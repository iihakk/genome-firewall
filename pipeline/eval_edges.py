"""Run the model against the edge-case benchmark.

Ordinary metrics cannot score these cases, because for several categories the correct answer is
not a label at all — it is a refusal. A model that confidently answers a chimeric sample is wrong
even when the label happens to match.

So each case is graded against an `expected_behaviour` contract:

    RESISTANT / SUSCEPTIBLE       must produce that call, confidently
    ABSTAIN                       must not produce a confident call
    ABSTAIN_OR_<LABEL>            either abstaining or the correct label is acceptable;
                                  the confident *opposite* is a failure
    ABSTAIN_IF_MECHANISM_LOST     graded on whether confidence tracks the surviving evidence

The failure that matters most is a confident SUSCEPTIBLE on a truly resistant genome — the call
that puts a patient on a drug that does nothing. It is counted separately as `lethal_errors`.

    python3 pipeline/eval_edges.py
"""

import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import canon_bvbrc  # noqa: E402
from firewall import Firewall  # noqa: E402
from validate import matrix, norm_drug  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def load_training():
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
    return feats, labels


def grade(expected, call, truth):
    """-> (passed, is_lethal)"""
    lethal = (truth == "Resistant" and call == "SUSCEPTIBLE")
    if expected == "ABSTAIN":
        return call == "INDETERMINATE", lethal
    if expected.startswith("ABSTAIN_OR_"):
        want = expected.split("ABSTAIN_OR_")[1]
        return call in ("INDETERMINATE", want), lethal
    if expected == "ABSTAIN_IF_MECHANISM_LOST":
        return call in ("INDETERMINATE", truth.upper()), lethal
    if expected == "DOCUMENTED_LIMITATION":
        # Scored but excluded from the headline pass rate: the information required is absent
        # from the feature space by construction, so this measures a boundary, not a defect.
        return None, lethal
    return call == expected, lethal


def main():
    bench = json.load(open(os.path.join(DATA, "edge_cases.json")))
    cases = bench["cases"]
    print(f"benchmark: {len(cases)} cases across {len(set(c['category'] for c in cases))} categories")

    feats, labels = load_training()
    train_ids = json.load(open(os.path.join(DATA, "split.json")))["train"]
    vocab = sorted({t for g in train_ids for t in feats.get(g, ())})
    known = set(vocab)
    print(f"training on {len(train_ids)} genomes, {len(vocab)} tokens")

    models = {}
    for drug in sorted({norm_drug(c["drug"]) for c in cases}):
        ids = [g for g in train_ids if drug in labels.get(g, {})]
        if len(ids) < 300:
            continue
        y = np.array([labels[g][drug] for g in ids])
        if min(y.sum(), len(y) - y.sum()) < 50:
            continue
        Xtr = matrix(feats, ids, vocab)
        mdl = CalibratedClassifierCV(
            HistGradientBoostingClassifier(max_iter=250, random_state=0),
            method="isotonic", cv=3).fit(Xtr, y)
        models[drug] = Firewall(mdl, vocab, Xtr, y, known)
        print(f"   model: {drug} (n={len(ids)})")

    results, per_cat = [], defaultdict(lambda: [0, 0, 0])
    for c in cases:
        drug = norm_drug(c["drug"])
        m = models.get(drug)
        if m is None:
            continue
        a = m.assess(set(c["features"]))
        prob, call = a["probability"], a["call"]
        ok, lethal = grade(c["expected_behaviour"], call, c["ground_truth"])
        per_cat[c["category"]][0] += 1
        per_cat[c["category"]][1] += int(bool(ok))
        per_cat[c["category"]][2] += int(lethal)
        if ok is None:
            per_cat[c["category"]][1] = -1  # marker: not scored
        results.append(dict(case_id=c["case_id"], category=c["category"], drug=drug,
                            ground_truth=c["ground_truth"], probability=round(prob, 3),
                            call=call, expected=c["expected_behaviour"],
                            reason=a["reason"],
                            neighbour_resistance_rate=a["neighbour_resistance_rate"],
                            passed=(None if ok is None else bool(ok)), lethal_error=bool(lethal)))

    scored = [r for r in results if r["passed"] is not None]
    tot = len(scored)
    passed = sum(r["passed"] for r in scored)
    lethal = sum(r["lethal_error"] for r in scored)
    print(f"\n{'category':<24}{'n':>4}{'passed':>9}{'lethal':>9}")
    print("-" * 48)
    for cat, (n, p, l) in sorted(per_cat.items()):
        if p < 0:
            print(f"{cat:<24}{n:>4}{'  not scored':>12}{l:>7}")
        else:
            print(f"{cat:<24}{n:>4}{p:>6} ({100*p//max(n,1):>3}%){l:>7}")
    print("-" * 48)
    print(f"{'TOTAL':<24}{tot:>4}{passed:>6} ({100*passed//max(tot,1):>3}%){lethal:>7}")
    print(f"\nlethal errors = confident SUSCEPTIBLE on a truly resistant genome: {lethal}")

    out = dict(n_cases=tot, passed=passed, pass_rate=round(passed / max(tot, 1), 3),
               lethal_errors=lethal,
               by_category={k: dict(n=v[0], passed=v[1], lethal=v[2]) for k, v in per_cat.items()},
               results=results)
    json.dump(out, open(os.path.join(DATA, "edge_case_results.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(DATA, 'edge_case_results.json')}")


if __name__ == "__main__":
    main()
