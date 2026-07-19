"""Does a model trained on Klebsiella work on E. coli it has never seen?

This is the hardest generalisation test available to us. Bacterial species differ in their
chromosomal background, their porin architecture and which determinants are native versus
acquired — blaSHV is chromosomal in Klebsiella and acquired in E. coli, for instance. A model that
transfers across that gap is using resistance biology; one that does not was fitting a species.

We report the honest three-way comparison per drug:

    within-species   trained and tested on E. coli          (upper bound)
    cross-species    trained on Klebsiella, tested on E. coli (the claim)
    rule             the same clinical lookup, which is species-agnostic by construction

The rule is the interesting comparator here. Lookup rules transfer perfectly across species
because they encode textbook mechanism, so if our model cannot beat the rule on an unseen
species, the honest conclusion is that it should not be used there.

    python3 pipeline/cross_species.py

Writes data/cross_species.json
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
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, build_vocab, canon, cohort, load_ncbi, matrix, norm_drug  # noqa: E402
from rules import RULES, coverage_ok  # noqa: E402


def load_bvbrc_species(taxon):
    """BV-BRC for an arbitrary species — gene presence only."""
    gp = os.path.join(DATA, f"genes_{taxon}.tsv")
    ap = os.path.join(DATA, f"amr_{taxon}.tsv")
    if not (os.path.exists(gp) and os.path.exists(ap)):
        return None, None
    genes = pd.read_csv(gp, sep="\t", dtype=str)
    genes["genome_id"] = genes.genome_id.str.strip('"')
    genes["product"] = genes["product"].fillna("").str.strip('"')
    genes["canon"] = genes["product"].map(canon)
    genes = genes.dropna(subset=["canon"])
    feats = genes.groupby("genome_id")["canon"].apply(set).to_dict()

    amr = pd.read_csv(ap, sep="\t", dtype=str)
    for c in ("genome_id", "antibiotic", "resistant_phenotype"):
        amr[c] = amr[c].fillna("").str.strip('"')
    amr = amr[amr.resistant_phenotype.isin(["Resistant", "Susceptible"])]
    amr["drug"] = amr.antibiotic.map(norm_drug)
    labels = defaultdict(dict)
    for g, d, p in zip(amr.genome_id, amr.drug, amr.resistant_phenotype):
        labels[g][d] = 1 if p == "Resistant" else 0
    return feats, dict(labels)


def gbm():
    return HistGradientBoostingClassifier(max_iter=250, random_state=0)


def main():
    kf, kl, _ = load_ncbi("klebsiella")
    print(f"Klebsiella (source, NCBI): {len(kf)} isolates")

    ef, el_ = load_bvbrc_species(562)
    if ef is None:
        sys.exit("E. coli data not found — run acquire.py 562 first")
    print(f"E. coli (target, BV-BRC): {len(ef)} genomes\n")

    print(f"{'drug':<30}{'n':>6}{'within':>9}{'cross':>8}{'rule':>8}{'transfer':>10}")
    print("-" * 71)
    rows, out = [], {}

    for drug in sorted(RULES):
        eids, ey = cohort(ef, el_, drug, min_n=200, min_minority=50)
        if eids is None:
            continue
        kids, ky = cohort(kf, kl, drug, min_n=150, min_minority=30)
        if kids is None:
            continue

        trig = RULES[drug]
        rule_pred = np.array([1 if (ef[g] & trig) else 0 for g in eids])
        if not coverage_ok(float(rule_pred.mean())):
            continue
        rule_b = balanced_accuracy_score(ey, rule_pred)

        # Cross-species: vocabulary is fixed by the SOURCE species. Anything E. coli carries that
        # Klebsiella never showed us is simply absent from the model's input — which is exactly
        # the handicap a real deployment on a new species would face.
        kvocab = build_vocab(kf, kids)
        if len(kvocab) < 3:
            continue
        m = CalibratedClassifierCV(gbm(), method="isotonic", cv=3).fit(
            matrix(kf, kids, kvocab), ky)
        Xe = matrix(ef, eids, kvocab)
        pc = m.predict_proba(Xe)[:, 1]
        cross_b = balanced_accuracy_score(ey, (pc > .5).astype(int))
        cross_auc = roc_auc_score(ey, pc) if len(np.unique(ey)) > 1 else None

        # Within-species upper bound, out-of-fold on E. coli itself.
        evocab = build_vocab(ef, eids)
        Xw = matrix(ef, eids, evocab)
        oof = np.zeros(len(ey))
        for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(Xw, ey):
            oof[b] = CalibratedClassifierCV(gbm(), method="isotonic", cv=3).fit(
                Xw[a], ey[a]).predict_proba(Xw[b])[:, 1]
        within_b = balanced_accuracy_score(ey, (oof > .5).astype(int))

        retained = cross_b / within_b if within_b > 0 else None
        rows.append((cross_b, within_b, rule_b))
        out[drug] = dict(n=len(eids), within=round(within_b, 3), cross=round(cross_b, 3),
                         cross_auc=round(float(cross_auc), 3) if cross_auc else None,
                         rule=round(rule_b, 3),
                         transfer_retained=round(retained, 3) if retained else None,
                         beats_rule=bool(cross_b - rule_b > 0.02))
        print(f"{drug:<30}{len(eids):>6}{within_b:>9.3f}{cross_b:>8.3f}{rule_b:>8.3f}"
              f"{100*retained:>9.0f}%")

    if not rows:
        sys.exit("no drugs had sufficient data in both species")

    cb = float(np.mean([r[0] for r in rows]))
    wb = float(np.mean([r[1] for r in rows]))
    rb = float(np.mean([r[2] for r in rows]))
    wins = sum(1 for d in out.values() if d["beats_rule"])
    print("-" * 71)
    print(f"\nwithin-species (E. coli, upper bound)  : {wb:.3f}")
    print(f"cross-species  (Klebsiella -> E. coli) : {cb:.3f}")
    print(f"clinical rule  (species-agnostic)      : {rb:.3f}")
    print(f"\ntransfer retains {100*cb/wb:.0f}% of within-species performance")
    print(f"cross-species model beats the rule on {wins}/{len(out)} drugs "
          f"({cb-rb:+.3f} mean)")

    verdict = ("transfers — usable on an unseen species" if cb - rb > 0.02
               else "does NOT transfer — do not deploy cross-species")
    print(f"verdict: {verdict}")

    json.dump(dict(summary=dict(within=round(wb, 3), cross=round(cb, 3), rule=round(rb, 3),
                                retained=round(cb / wb, 3), beats_rule_on=wins,
                                drugs=len(out), gain_over_rule=round(cb - rb, 3),
                                verdict=verdict),
                   per_drug=out),
              open(os.path.join(DATA, "cross_species.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(DATA, 'cross_species.json')}")


if __name__ == "__main__":
    main()
