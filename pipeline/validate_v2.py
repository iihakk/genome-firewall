"""Five-tier validation on the rebuilt feature set.

Tiers, each removing a different crutch:

  1. RANDOM       optimistic baseline — what most work reports
  2. CLONE-AWARE  isolates with identical genotype profiles never straddle the split
  3. HOLDOUT      quarantined before modelling, touched once
  4. EXTERNAL     trained on NCBI (genes+mutations), tested on BV-BRC (genes only) —
                  a different curation AND a degraded feature set
  5. TEMPORAL     trained on older isolates, tested on later ones
  6. GEOGRAPHIC   trained on some countries, tested on others

Plus a rule comparison per drug, so every accuracy claim is stated against the alternative a
clinician already has.

    python3 pipeline/validate_v2.py

Writes data/validation_v2.json
"""

import json
import os
import sys

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, StratifiedKFold, train_test_split

sys.path.insert(0, os.path.dirname(__file__))
from features import (DATA, build_vocab, cohort, load_bvbrc, load_ncbi,  # noqa: E402
                      matrix, norm_drug)
from rules import RULES  # noqa: E402

REPEATS = 8
HOLDOUT_FRAC = 0.20


def gbm():
    return HistGradientBoostingClassifier(max_iter=250, random_state=0)


def calibrated():
    return CalibratedClassifierCV(gbm(), method="isotonic", cv=3)


def auc(model, X, y):
    if len(np.unique(y)) < 2:
        return None
    return roc_auc_score(y, model.predict_proba(X)[:, 1])


def main():
    print("1. loading NCBI (primary — genes + mutations + truncations) ...")
    nf, nl, nm = load_ncbi("klebsiella")
    print(f"   {len(nf)} isolates")

    print("2. loading BV-BRC (external — gene presence only) ...")
    bf, bl, bm = load_bvbrc(573)
    print(f"   {len(bf)} genomes")

    # Quarantine by clone before anything touches the data.
    ids_all = sorted(nf)
    clones = np.array([nm[g]["clone"] for g in ids_all])
    tr_i, ho_i = next(GroupShuffleSplit(n_splits=1, test_size=HOLDOUT_FRAC,
                                        random_state=1234).split(ids_all, groups=clones))
    train_ids = [ids_all[i] for i in tr_i]
    hold_ids = [ids_all[i] for i in ho_i]
    print(f"3. locked holdout: {len(train_ids)} train / {len(hold_ids)} quarantined")
    json.dump({"train": train_ids, "holdout": hold_ids},
              open(os.path.join(DATA, "split_v2.json"), "w"))

    drugs = sorted({d for g in train_ids for d in nl[g]})
    report = {}
    print(f"\n{'drug':<30}{'n':>5}{'rand':>7}{'clone':>7}{'hold':>7}{'ext':>7}"
          f"{'temp':>7}{'geo':>7}{'rule':>7}{'model':>7}")
    print("-" * 91)

    for drug in drugs:
        ids, y = cohort({g: nf[g] for g in train_ids}, nl, drug, min_n=150, min_minority=30)
        if ids is None:
            continue
        vocab = build_vocab(nf, ids)
        if len(vocab) < 3:
            continue
        X = matrix(nf, ids, vocab)
        grp = np.array([nm[g]["clone"] for g in ids])

        # 1 + 2
        rnd, cln = [], []
        for s in range(REPEATS):
            a, b = train_test_split(np.arange(len(y)), test_size=.3, random_state=s, stratify=y)
            rnd.append(auc(gbm().fit(X[a], y[a]), X[b], y[b]) or np.nan)
            a2, b2 = next(GroupShuffleSplit(n_splits=1, test_size=.3,
                                            random_state=s).split(X, y, groups=grp))
            if len(np.unique(y[b2])) > 1:
                cln.append(auc(gbm().fit(X[a2], y[a2]), X[b2], y[b2]) or np.nan)

        model = calibrated().fit(X, y)

        # 3 locked holdout
        hid, hy = cohort({g: nf[g] for g in hold_ids}, nl, drug, min_n=30, min_minority=5)
        ho = auc(model, matrix(nf, hid, vocab), hy) if hid else None
        brier = (brier_score_loss(hy, model.predict_proba(matrix(nf, hid, vocab))[:, 1])
                 if hid and len(np.unique(hy)) > 1 else None)

        # 4 external: BV-BRC, different curation, no mutation features available
        ext = None
        eid, ey = cohort(bf, bl, drug, min_n=100, min_minority=20)
        if eid:
            ext = auc(model, matrix(bf, eid, vocab), ey)

        # 5 temporal
        tmp = None
        yrs = np.array([int(nm[g]["year"]) if str(nm[g]["year"]).isdigit() else 0 for g in ids])
        dated = yrs > 0
        if dated.sum() > 150:
            cut = int(np.percentile(yrs[dated], 70))
            old = np.where(dated & (yrs <= cut))[0]
            new = np.where(dated & (yrs > cut))[0]
            if len(old) > 100 and len(new) > 25 and len(np.unique(y[new])) > 1 \
                    and min(y[old].sum(), len(old) - y[old].sum()) > 10:
                tmp = auc(gbm().fit(X[old], y[old]), X[new], y[new])

        # 6 geographic
        geo = None
        gs = np.array([nm[g]["geo"] or "?" for g in ids])
        uniq = [u for u in set(gs) if u != "?" and (gs == u).sum() >= 25]
        if len(uniq) >= 2:
            held = uniq[0]
            a3 = np.where(gs != held)[0]
            b3 = np.where(gs == held)[0]
            if len(np.unique(y[b3])) > 1 and min(y[a3].sum(), len(a3) - y[a3].sum()) > 10:
                geo = auc(gbm().fit(X[a3], y[a3]), X[b3], y[b3])

        # rule vs model, out-of-fold, same isolates
        trig = RULES.get(drug)
        rule_b = model_b = None
        if trig:
            rule_b = balanced_accuracy_score(y, np.array([1 if (nf[g] & trig) else 0
                                                          for g in ids]))
            oof = np.zeros(len(y))
            for a4, b4 in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
                oof[b4] = calibrated().fit(X[a4], y[a4]).predict_proba(X[b4])[:, 1]
            model_b = balanced_accuracy_score(y, (oof > .5).astype(int))

        def r3(v):
            return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 3)

        report[drug] = dict(
            n=len(ids), pct_resistant=round(100 * float(y.mean())), n_features=len(vocab),
            random=r3(np.nanmean(rnd)), clone=r3(np.nanmean(cln)) if cln else None,
            holdout=r3(ho), n_holdout=len(hid) if hid else 0, external=r3(ext),
            n_external=len(eid) if eid else 0, temporal=r3(tmp), geographic=r3(geo),
            brier=r3(brier), rule_balanced_acc=r3(rule_b), model_balanced_acc=r3(model_b))
        r = report[drug]
        f = lambda k: f"{r[k]:.3f}" if r[k] is not None else "  -  "  # noqa: E731
        print(f"{drug:<30}{r['n']:>5}{f('random'):>7}{f('clone'):>7}{f('holdout'):>7}"
              f"{f('external'):>7}{f('temporal'):>7}{f('geographic'):>7}"
              f"{f('rule_balanced_acc'):>7}{f('model_balanced_acc'):>7}")

    def avg(k):
        v = [r[k] for r in report.values() if r.get(k) is not None]
        return round(float(np.mean(v)), 3) if v else None

    gains = [r["model_balanced_acc"] - r["rule_balanced_acc"] for r in report.values()
             if r.get("rule_balanced_acc") is not None and r.get("model_balanced_acc") is not None]
    summary = dict(
        drugs=len(report), train=len(train_ids), holdout=len(hold_ids), external=len(bf),
        mean=dict(random=avg("random"), clone=avg("clone"), holdout=avg("holdout"),
                  external=avg("external"), temporal=avg("temporal"),
                  geographic=avg("geographic")),
        rule=dict(mean_rule=avg("rule_balanced_acc"), mean_model=avg("model_balanced_acc"),
                  mean_gain=round(float(np.mean(gains)), 3) if gains else None,
                  wins=sum(1 for g in gains if g > 0.02),
                  ties=sum(1 for g in gains if abs(g) <= 0.02),
                  losses=sum(1 for g in gains if g < -0.02)))
    json.dump(dict(summary=summary, per_drug=report),
              open(os.path.join(DATA, "validation_v2.json"), "w"), indent=1)

    print("\n" + "=" * 66)
    print(f"MEAN ACROSS {len(report)} ANTIBIOTICS")
    print("=" * 66)
    for k, lbl in [("random", "1. random split (optimistic)"),
                   ("clone", "2. clone-aware split"),
                   ("holdout", "3. locked holdout"),
                   ("external", "4. EXTERNAL (BV-BRC, no mutation features)"),
                   ("temporal", "5. temporal"),
                   ("geographic", "6. geographic")]:
        v = summary["mean"][k]
        print(f"   {lbl:<46} {v if v else 'n/a'}")
    rl = summary["rule"]
    print(f"\n   vs clinical rule: model {rl['mean_model']} vs rule {rl['mean_rule']}  "
          f"({rl['mean_gain']:+})")
    print(f"   wins {rl['wins']} / ties {rl['ties']} / losses {rl['losses']}")
    print(f"\nwrote {os.path.join(DATA, 'validation_v2.json')}")


if __name__ == "__main__":
    main()
