"""Where the clinical lookup rule fails — and whether we catch it.

Average accuracy hides the thing a clinician actually cares about. What matters is the specific
isolates where the tool they already use gives the wrong answer, and in particular the direction
of that error:

  FALSE-SUSCEPTIBLE   no known determinant found, so the rule says the drug will work.
                      It does not. The patient receives an ineffective antibiotic while a serious
                      infection advances. This is the error that kills.

  FALSE-RESISTANT     a determinant is present, so the rule says the drug will fail. It does not.
                      A usable antibiotic is discarded, pushing therapy toward broader agents and
                      accelerating resistance.

For each failure we also ask WHY the rule missed it — is there a target mutation, porin loss, or
an efflux determinant the rule ignores? — which turns a list of errors into a map of the
mechanisms current practice cannot see.

    python3 pipeline/discordance.py

Writes data/discordance.json
"""

import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, build_vocab, cohort, load_ncbi, matrix  # noqa: E402
from rules import RULES, coverage_ok  # noqa: E402

# Mechanisms a gene-presence rule structurally cannot express.
MUTATION = lambda t: t.startswith(("POINT:", "TRUNC:"))          # noqa: E731
EFFLUX = {"oqxab", "acr", "acrab", "acref", "mdt", "mdtabc", "emr", "emrab", "mdf",
          "mar", "mara", "marr", "ramr", "acrr", "oqxr", "kpnef", "kdeа"}


def explain(tokens, trig):
    """Why might the rule have missed this isolate's resistance?"""
    muts = sorted(t for t in tokens if MUTATION(t))
    eff = sorted(t for t in tokens if t in EFFLUX)
    porin = sorted(t for t in tokens if "ompk" in t)
    if porin:
        return "porin loss", porin
    if muts:
        return "target mutation", muts
    if eff:
        return "efflux / regulator", eff
    if tokens - trig:
        return "determinant outside rule", sorted(tokens - trig)[:4]
    return "no genomic explanation", []


def main():
    feats, labels, meta = load_ncbi("klebsiella")
    print(f"isolates: {len(feats)}\n")

    out, totals, skipped = {}, Counter(), []
    mech = defaultdict(Counter)
    print(f"{'drug':<28}{'n':>5}{'rule wrong':>12}{'false-S':>9}{'model':>8}{'recovered':>11}")
    print("-" * 74)

    for drug, trig in RULES.items():
        ids, y = cohort(feats, labels, drug, min_n=120, min_minority=25)
        if ids is None:
            continue
        vocab = build_vocab(feats, ids)
        if len(vocab) < 3:
            continue
        X = matrix(feats, ids, vocab)

        rule = np.array([1 if (feats[g] & trig) else 0 for g in ids])
        # Skip drugs where the rule is not a real baseline (never fires, or fires on everything).
        if not coverage_ok(float(rule.mean())):
            print(f"{drug:<28}{len(ids):>5}   skipped — rule fires on "
                  f"{100*rule.mean():.0f}% of isolates, not a valid baseline")
            skipped.append((drug, round(float(rule.mean()), 3)))
            continue
        oof = np.zeros(len(y))
        for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
            m = CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=250,
                                                                     random_state=0),
                                       method="isotonic", cv=3).fit(X[a], y[a])
            oof[b] = m.predict_proba(X[b])[:, 1]
        pred = (oof > 0.5).astype(int)

        wrong = np.where(rule != y)[0]
        false_s = np.where((rule == 0) & (y == 1))[0]     # the dangerous direction
        false_r = np.where((rule == 1) & (y == 0))[0]
        recovered = int((pred[wrong] == y[wrong]).sum()) if len(wrong) else 0
        rec_fs = int((pred[false_s] == 1).sum()) if len(false_s) else 0

        cases = []
        for i in false_s:
            why, ev = explain(feats[ids[i]], trig)
            mech[drug][why] += 1
            totals[why] += 1
            cases.append(dict(isolate=ids[i], drug=drug, truth="Resistant",
                              rule_says="Susceptible", model_prob=round(float(oof[i]), 3),
                              model_says="Resistant" if pred[i] else "Susceptible",
                              model_correct=bool(pred[i] == 1),
                              missed_mechanism=why, evidence=ev))

        totals["false_susceptible"] += len(false_s)
        totals["false_resistant"] += len(false_r)
        totals["recovered_false_susceptible"] += rec_fs

        out[drug] = dict(
            n=len(ids), rule_wrong=int(len(wrong)),
            false_susceptible=int(len(false_s)), false_resistant=int(len(false_r)),
            model_correct_on_rule_errors=recovered,
            model_recovers_false_susceptible=rec_fs,
            recovery_rate=round(rec_fs / len(false_s), 3) if len(false_s) else None,
            mechanisms=dict(mech[drug]), examples=cases[:8])

        pct = 100 * len(wrong) / len(ids)
        rr = f"{100*rec_fs/len(false_s):.0f}%" if len(false_s) else "  -"
        print(f"{drug:<28}{len(ids):>5}{len(wrong):>7} ({pct:>3.0f}%){len(false_s):>9}"
              f"{recovered:>8}{rr:>11}")

    fs = totals["false_susceptible"]
    rec = totals["recovered_false_susceptible"]
    print("-" * 74)
    print(f"\nAcross all drugs:")
    print(f"  isolates the rule calls SUSCEPTIBLE that are actually RESISTANT : {fs}")
    print(f"  of those, our model correctly calls RESISTANT                   : {rec}"
          f"  ({100*rec/max(fs,1):.0f}%)")
    print(f"  isolates the rule calls RESISTANT that are actually SUSCEPTIBLE : "
          f"{totals['false_resistant']}")

    print(f"\nWhy the rule missed the dangerous cases:")
    for why, c in totals.most_common():
        if why in ("false_susceptible", "false_resistant", "recovered_false_susceptible"):
            continue
        print(f"  {why:<28} {c:>5}  ({100*c/max(fs,1):.0f}%)")

    if skipped:
        print(f"\nexcluded (rule not a valid baseline): "
              f"{', '.join(f'{d} {100*r:.0f}%' for d, r in skipped)}")
    json.dump(dict(
        excluded_invalid_rule=skipped,
        summary=dict(false_susceptible=fs, recovered=rec,
                     recovery_rate=round(rec / max(fs, 1), 3),
                     false_resistant=totals["false_resistant"],
                     mechanisms={k: v for k, v in totals.items()
                                 if k not in ("false_susceptible", "false_resistant",
                                              "recovered_false_susceptible")}),
        per_drug=out), open(os.path.join(DATA, "discordance.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(DATA, 'discordance.json')}")


if __name__ == "__main__":
    main()
