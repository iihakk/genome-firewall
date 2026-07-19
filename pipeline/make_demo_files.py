"""Produce uploadable demo profiles from genuinely unseen isolates.

Every file is a real isolate drawn from the quarantined holdout — never used in training, and
excluded from the seeded caseload the application ships with, so uploading one exercises the model
on data it has not encountered in any form.

The determinants are written in raw AMRFinderPlus notation (blaKPC-2, gyrA_S83I=POINT,
ompK35_E42RfsTer) rather than our internal vocabulary, so the upload path performs the same
normalisation a real submission would.

    python3 pipeline/make_demo_files.py

Writes demo-files/*.json
"""

import csv
import json
import os
import pickle
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, HERE, canon_raw  # noqa: E402

csv.field_size_limit(10 ** 7)
OUT = os.path.join(HERE, "demo-files")

WARDS = ["Intensive Care", "Haematology", "Renal", "Emergency", "Surgery"]
CLINICIANS = ["Dr. R. Okonkwo", "Dr. M. Lindqvist", "Dr. S. Haddad", "Dr. P. Ramanathan"]


def raw_profiles():
    """asm_acc -> raw AMRFinderPlus tokens, straight from the NCBI dump."""
    src = os.path.join(DATA, "ncbi_amr_kleb.tsv")
    rd = csv.reader(open(src, newline="", encoding="utf-8", errors="replace"), delimiter="\t")
    h = next(rd)
    iA, iG, iAcc = h.index("AST_phenotypes"), h.index("AMR_genotypes"), h.index("asm_acc")
    iSrc = h.index("isolation_source")
    out = {}
    for r in rd:
        if len(r) <= iA or not r[iA] or r[iA] in ("NULL", "-"):
            continue
        toks = [t.strip() for t in (r[iG] if len(r) > iG else "").split(",") if t.strip()]
        if toks:
            out[r[iAcc]] = {"tokens": toks, "source": (r[iSrc] or "").lower(),
                            "ast": r[iA]}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    split = json.load(open(os.path.join(DATA, "split_v2.json")))
    holdout = set(split["holdout"])
    shipped = {s["genomeId"] for s in
               json.load(open(os.path.join(HERE, "web", "src", "data", "seed.json")))["specimens"]}
    profiles = raw_profiles()

    # Unseen twice over: quarantined from training AND absent from the shipped caseload.
    pool = [a for a in holdout if a in profiles and a not in shipped]
    print(f"holdout {len(holdout)} · with genotype {len(pool)} · shipped {len(shipped)}")

    def canon_set(toks):
        return {c for c in (canon_raw(t) for t in toks) if c}

    # Pick profiles that between them exercise every behaviour worth demonstrating.
    # What the models were actually trained on. A determinant outside this set is what trips the
    # novelty gate, so selecting the "sparse" demo on determinant count alone is not enough —
    # a small clean genome sails straight through and the file misrepresents itself.
    known = set(pickle.load(open(os.path.join(DATA, "models.pkl"), "rb"))["known"])

    scored = []
    for a in pool:
        p = profiles[a]
        cs = canon_set(p["tokens"])
        scored.append({
            "acc": a,
            "n": len(cs),
            "mut": sum(1 for c in cs if c.startswith(("POINT:", "TRUNC:"))),
            "carb": any(c in {"blakpc", "blandm", "blaoxa-48", "blavim"} for c in cs),
            "novel": len(cs - known),
            "profile": p,
        })

    wanted = [
        ("treatable-isolate", lambda s: not s["carb"] and s["mut"] == 0 and s["novel"] == 0 and 3 <= s["n"] <= 6,
         "Lightly armed isolate — the case where the system clears therapy rather than refusing it"),
        ("carbapenemase-mutations", lambda s: s["carb"] and s["mut"] >= 2,
         "Carbapenemase plus target mutations — the multidrug case"),
        ("mutations-no-carbapenemase", lambda s: not s["carb"] and s["mut"] >= 2,
         "Chromosomal mutations only — where gene lookup reports susceptible"),
        ("unfamiliar-machinery", lambda s: s["n"] <= 8 and s["novel"] >= 1,
         "Carries machinery absent from training — should trip the novelty gate"),
        ("rich-profile", lambda s: s["n"] >= 14,
         "Heavily armed isolate — most drugs expected to fail"),
    ]

    made = []
    used = set()
    for name, pred, note in wanted:
        pick = next((s for s in sorted(scored, key=lambda x: -x["n"])
                     if pred(s) and s["acc"] not in used), None)
        if not pick:
            print(f"  (no isolate matched {name})")
            continue
        used.add(pick["acc"])
        i = len(made)
        payload = {
            "accession": f"DEMO-{2601 + i}",
            "organism": "Klebsiella pneumoniae",
            "source": pick["profile"]["source"] or "blood culture",
            "ward": WARDS[i % len(WARDS)],
            "requestedBy": CLINICIANS[i % len(CLINICIANS)],
            "sequencedFrom": pick["acc"],
            "note": note,
            "determinants": pick["profile"]["tokens"],
        }
        path = os.path.join(OUT, f"{name}.json")
        json.dump(payload, open(path, "w"), indent=1)
        made.append((name, pick["acc"], pick["n"], pick["mut"], pick["profile"]["ast"][:60]))
        print(f"  {name:<28} {pick['acc']:<18} {pick['n']:>2} determinants, {pick['mut']} mutations")

    readme = ["# Demo profiles", "",
              "Real *Klebsiella pneumoniae* isolates from the quarantined holdout. None were used",
              "in training, and none appear in the caseload the application ships with — uploading",
              "one runs the model on data it has genuinely never seen.",
              "",
              "Determinants are in raw AMRFinderPlus notation, so the upload path performs the same",
              "normalisation a real laboratory submission would.", "",
              "| file | source isolate | determinants | mutations |",
              "|---|---|---|---|"]
    for name, acc, n, mut, _ in made:
        readme.append(f"| `{name}.json` | {acc} | {n} | {mut} |")
    open(os.path.join(OUT, "README.md"), "w").write("\n".join(readme) + "\n")
    print(f"\nwrote {len(made)} profiles to {OUT}")


if __name__ == "__main__":
    main()
