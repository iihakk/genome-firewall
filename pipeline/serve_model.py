"""Train once, persist, then predict on demand.

Backs the application's live analysis. The interface uploads a determinant profile and this
returns real predictions from the same models the validation report describes — not a lookup of
precomputed answers.

    python3 pipeline/serve_model.py --build          # train and cache the models
    python3 pipeline/serve_model.py --predict f.json # score a profile, print JSON

The profile format is what AMRFinderPlus produces for a genome, which is what a laboratory would
already have after sequencing:

    {"accession": "...", "organism": "Klebsiella pneumoniae",
     "determinants": ["blaKPC-2", "gyrA_S83I=POINT", "ompK35_E42RfsTer", ...]}
"""

import argparse
import json
import os
import pickle
import re
import sys
import time

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, build_vocab, canon_raw, cohort, load_ncbi  # noqa: E402
from features import matrix as feat_matrix  # noqa: E402
from firewall import Firewall  # noqa: E402

MODEL_PATH = os.path.join(DATA, "models.pkl")
DRUGS = ["meropenem", "ertapenem", "ciprofloxacin", "levofloxacin", "ceftazidime",
         "ceftriaxone", "gentamicin", "amikacin", "trimethoprim-sulfamethoxazole",
         "piperacillin-tazobactam"]


normalise = canon_raw


def build():
    t0 = time.time()
    feats, labels, _ = load_ncbi("klebsiella")
    split = json.load(open(os.path.join(DATA, "split_v2.json")))
    train_ids = split["train"]
    known = {t for g in train_ids for t in feats.get(g, ())}
    print(f"training on {len(train_ids)} quarantine-excluded isolates")

    bundle = {"known": sorted(known), "drugs": {}}
    for drug in DRUGS:
        ids, y = cohort({g: feats[g] for g in train_ids}, labels, drug,
                        min_n=150, min_minority=30)
        if ids is None:
            continue
        vocab = build_vocab(feats, ids)
        if len(vocab) < 3:
            continue
        X = feat_matrix(feats, ids, vocab)
        mdl = CalibratedClassifierCV(
            HistGradientBoostingClassifier(max_iter=250, random_state=0),
            method="isotonic", cv=3).fit(X, y)
        bundle["drugs"][drug] = {"model": mdl, "vocab": vocab, "X": X, "y": y, "n": len(ids)}
        print(f"   {drug:<32} n={len(ids):>4}  features={len(vocab)}")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)
    print(f"\ncached {len(bundle['drugs'])} models -> {MODEL_PATH}  ({time.time()-t0:.0f}s)")


def predict(profile):
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    known = set(bundle["known"])

    raw = profile.get("determinants", [])
    canonical, unmapped = set(), []
    for r in raw:
        c = normalise(r)
        if c:
            canonical.add(c)
        else:
            unmapped.append(r)

    results = []
    novel = set()
    for drug, d in bundle["drugs"].items():
        fw = Firewall(d["model"], d["vocab"], d["X"], d["y"], known)
        a = fw.assess(canonical)
        # Two distinct kinds of "we don't know this": a token the vocabulary could not normalise
        # at all, and one that normalised cleanly but never appeared in training. Only the second
        # trips the novelty gate, so report them separately rather than letting the gate's reason
        # contradict a count of zero on screen.
        novel.update(a["unknown_machinery"])
        results.append({
            "drug": drug,
            "call": a["call"],
            "probability": a["probability"],
            "reason": a["reason"],
            "unknownMachinery": a["unknown_machinery"],
            "neighbourResistanceRate": a["neighbour_resistance_rate"],
        })

    order = {"SUSCEPTIBLE": 0, "INDETERMINATE": 1, "RESISTANT": 2}
    results.sort(key=lambda r: (order[r["call"]],
                                r["probability"] if r["call"] == "SUSCEPTIBLE"
                                else -r["probability"]))
    return {
        "accession": profile.get("accession", "unknown"),
        "organism": profile.get("organism", "Klebsiella pneumoniae"),
        "source": profile.get("source"),
        "determinantsSubmitted": len(raw),
        "determinantsRecognised": sorted(canonical),
        "determinantsUnrecognised": unmapped,
        "determinantsNovel": sorted(novel),
        "results": results,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--predict")
    args = ap.parse_args()
    if args.build:
        build()
    elif args.predict:
        print(json.dumps(predict(json.load(open(args.predict))), indent=1))
    else:
        ap.print_help()
