"""Does the firewall still refuse to answer 72% of the time?

That figure came from the previous build and was the single worst thing about the system: a tool
that says "I don't know" seven times out of ten is not clinically useful. The diagnosis was that
most refusals were a vocabulary artifact — NCBI tokens absent from a BV-BRC-trained vocabulary
tripped the novelty gate on a schema difference rather than on anything genuinely novel.

The rebuilt feature set trains and predicts through one shared vocabulary, so this re-measures
deferral honestly, and — critically — measures it against the safety constraint it exists to
serve. Coverage is only worth having if lethal errors do not rise with it.

    python3 pipeline/deferral.py

Writes data/deferral.json
"""

import json
import os
import sys

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, build_vocab, cohort, load_ncbi, matrix  # noqa: E402
from firewall import Firewall  # noqa: E402


def main():
    feats, labels, meta = load_ncbi("klebsiella")
    split = json.load(open(os.path.join(DATA, "split_v2.json")))
    train_ids, hold_ids = split["train"], split["holdout"]
    known = {t for g in train_ids for t in feats.get(g, ())}
    print(f"train {len(train_ids)} / holdout {len(hold_ids)} · shared vocabulary {len(known)}\n")

    print(f"{'drug':<30}{'n':>5}{'defer':>8}{'answered acc':>14}"
          f"{'lethal':>8}{'coverage acc':>14}")
    print("-" * 79)

    rows, out = [], {}
    for drug in sorted({d for g in train_ids for d in labels[g]}):
        ids, y = cohort({g: feats[g] for g in train_ids}, labels, drug,
                        min_n=150, min_minority=30)
        if ids is None:
            continue
        vocab = build_vocab(feats, ids)
        if len(vocab) < 3:
            continue
        X = matrix(feats, ids, vocab)

        hid, hy = cohort({g: feats[g] for g in hold_ids}, labels, drug,
                         min_n=25, min_minority=4)
        if hid is None:
            continue
        Xh = matrix(feats, hid, vocab)

        mdl = CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=250,
                                                                    random_state=0),
                                     method="isotonic", cv=3).fit(X, y)
        fw = Firewall(mdl, vocab, X, y, known)

        calls = [fw.assess(feats[g]) for g in hid]
        answered = np.array([c["call"] != "INDETERMINATE" for c in calls])
        pred = np.array([1 if c["call"] == "RESISTANT" else 0 for c in calls])

        defer = 1 - answered.mean()
        acc_ans = (pred[answered] == hy[answered]).mean() if answered.sum() else None
        acc_all = (pred == hy).mean()
        # The error that kills: a confident SUSCEPTIBLE on a resistant isolate.
        lethal = int(((pred == 0) & (hy == 1) & answered).sum())

        reasons = {}
        for c in calls:
            if c["reason"]:
                k = c["reason"].split("—")[0].strip()[:44]
                reasons[k] = reasons.get(k, 0) + 1

        rows.append((defer, acc_ans, acc_all, lethal, len(hid)))
        out[drug] = dict(n=len(hid), deferral=round(float(defer), 3),
                         answered_accuracy=round(float(acc_ans), 3) if acc_ans else None,
                         accuracy_if_forced=round(float(acc_all), 3),
                         lethal_errors=lethal, reasons=reasons)
        aa = f"{acc_ans:.3f}" if acc_ans is not None else "  -  "
        print(f"{drug:<30}{len(hid):>5}{100*defer:>7.0f}%{aa:>14}{lethal:>8}"
              f"{acc_all:>14.3f}")

    d = float(np.mean([r[0] for r in rows]))
    aa = float(np.mean([r[1] for r in rows if r[1] is not None]))
    af = float(np.mean([r[2] for r in rows]))
    lt = int(sum(r[3] for r in rows))
    n = int(sum(r[4] for r in rows))
    print("-" * 79)
    print(f"\nmean deferral rate                : {100*d:.0f}%   (previous build: 72%)")
    print(f"accuracy on answered cases        : {aa:.3f}")
    print(f"accuracy if forced to answer all  : {af:.3f}")
    print(f"lethal errors among answered      : {lt} across {n} predictions")
    print(f"\nabstaining buys {aa-af:+.3f} accuracy on the cases it does answer.")

    json.dump(dict(summary=dict(mean_deferral=round(d, 3),
                                answered_accuracy=round(aa, 3),
                                accuracy_if_forced=round(af, 3),
                                accuracy_gain=round(aa - af, 3),
                                lethal_errors=lt, predictions=n),
                   per_drug=out),
              open(os.path.join(DATA, "deferral.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(DATA, 'deferral.json')}")


if __name__ == "__main__":
    main()
