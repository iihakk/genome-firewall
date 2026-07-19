"""Compare the model against the rule-based baseline it has to justify replacing.

The obvious objection to any of this is: "why not just look up the resistance genes?" That is
what ResFinder-style tools do — if a carbapenemase is present, call carbapenem resistance. If the
model cannot beat that rule on an independent dataset, the model is not earning its complexity.

Evaluated on the NCBI external set (independent curation, independent gene caller, isolates
overlapping BV-BRC removed), so neither approach is scored on data it grew up with.

    python3 pipeline/baseline.py
"""

import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import canon_bvbrc  # noqa: E402
from validate import load_ncbi, matrix, norm_drug  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

CARBA = {"blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "blaOXA-carbapenemase"}
ESBL = {"blaCTX-M", "blaSHV", "blaTEM", "blaGES", "blaPER", "blaVEB"}

# The standard genotype->phenotype rules, as a lookup tool would apply them.
RULES = {
    "meropenem": CARBA,
    "imipenem": CARBA,
    "ertapenem": CARBA,
    "ceftazidime": CARBA | ESBL | {"blaAmpC"},
    "ceftriaxone": CARBA | ESBL | {"blaAmpC"},
    "cefotaxime": CARBA | ESBL | {"blaAmpC"},
    "cefepime": CARBA | ESBL,
    "ciprofloxacin": {"qnrA", "qnrB", "qnrS", "qnr_other", "aac(6')"},
    "levofloxacin": {"qnrA", "qnrB", "qnrS", "qnr_other"},
    "gentamicin": {"aac(3)", "rmt_16S_methylase"},
    "tobramycin": {"aac(3)", "aac(6')", "ant(2'')", "rmt_16S_methylase"},
    "amikacin": {"aac(6')", "rmt_16S_methylase"},
    "trimethoprim-sulfamethoxazole": {"sul", "dfr"},
    "tetracycline": {"tet"},
}


def main():
    genes = pd.read_csv(os.path.join(DATA, "genes_573.tsv"), sep="\t", dtype=str)
    genes["genome_id"] = genes.genome_id.str.strip('"')
    genes["product"] = genes["product"].fillna("").str.strip('"')
    genes["canon"] = genes["product"].map(canon_bvbrc)
    genes = genes.dropna(subset=["canon"])
    feats = genes.groupby("genome_id")["canon"].apply(set).to_dict()

    amr = pd.read_csv(os.path.join(DATA, "amr_573.tsv"), sep="\t", dtype=str)
    for c in ("genome_id", "antibiotic", "resistant_phenotype"):
        amr[c] = amr[c].fillna("").str.strip('"')
    amr = amr[amr.resistant_phenotype.isin(["Resistant", "Susceptible"])]
    amr["drug"] = amr.antibiotic.map(norm_drug)
    labels = defaultdict(dict)
    for g, d, p in zip(amr.genome_id, amr.drug, amr.resistant_phenotype):
        labels[g][d] = 1 if p == "Resistant" else 0

    acc = pd.read_csv(os.path.join(DATA, "bvbrc_accessions.tsv"), sep="\t", dtype=str)
    ex_acc = set(acc.assembly_accession.dropna().str.split(".").str[0])
    ex_sra = set(acc.sra_accession.dropna())
    nfeats, nlabels, _ = load_ncbi("klebsiella", ex_acc, ex_sra)

    train_ids = json.load(open(os.path.join(DATA, "split.json")))["train"]
    vocab = sorted({t for g in train_ids for t in feats.get(g, ())} |
                   {t for s in nfeats.values() for t in s})

    print(f"\n{'drug':<32}{'n':>5}{'RULE bAcc':>11}{'MODEL bAcc':>12}{'MODEL AUC':>11}{'delta':>8}")
    print("-" * 79)
    out, deltas = {}, []
    for drug, trigger in RULES.items():
        ids = [a for a in nfeats if drug in nlabels.get(a, {})]
        if len(ids) < 40:
            continue
        y = np.array([nlabels[a][drug] for a in ids])
        if len(np.unique(y)) < 2:
            continue

        rule_pred = np.array([1 if (nfeats[a] & trigger) else 0 for a in ids])
        rule_b = balanced_accuracy_score(y, rule_pred)

        tr = [g for g in train_ids if drug in labels.get(g, {})]
        if len(tr) < 300:
            continue
        ytr = np.array([labels[g][drug] for g in tr])
        if min(ytr.sum(), len(ytr) - ytr.sum()) < 50:
            continue
        m = CalibratedClassifierCV(
            HistGradientBoostingClassifier(max_iter=250, random_state=0),
            method="isotonic", cv=3).fit(matrix(feats, tr, vocab), ytr)
        p = m.predict_proba(matrix(nfeats, ids, vocab))[:, 1]
        model_b = balanced_accuracy_score(y, (p > .5).astype(int))
        model_auc = roc_auc_score(y, p)

        d = model_b - rule_b
        deltas.append(d)
        out[drug] = dict(n=len(ids), rule_balanced_acc=round(rule_b, 3),
                         model_balanced_acc=round(model_b, 3),
                         model_auc=round(model_auc, 3), delta=round(d, 3))
        flag = "  <-- rule wins" if d < -0.02 else ""
        print(f"{drug:<32}{len(ids):>5}{rule_b:>11.3f}{model_b:>12.3f}"
              f"{model_auc:>11.3f}{d:>+8.3f}{flag}")

    print("-" * 79)
    wins = sum(1 for v in out.values() if v["delta"] > 0.02)
    ties = sum(1 for v in out.values() if abs(v["delta"]) <= 0.02)
    loss = sum(1 for v in out.values() if v["delta"] < -0.02)
    print(f"model better on {wins}, comparable on {ties}, worse on {loss} of {len(out)} drugs")
    print(f"mean balanced-accuracy gain over the lookup rule: {np.mean(deltas):+.3f}")
    json.dump(out, open(os.path.join(DATA, "baseline_comparison.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(DATA, 'baseline_comparison.json')}")


if __name__ == "__main__":
    main()
