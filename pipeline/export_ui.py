"""Export everything the interface needs, from the rebuilt model.

The UI never calls a model. Predictions are computed here and embedded, so the demo loads
instantly and cannot fail live during recording. The tech video shows this script running.

Carries the four things the previous export could not:
  * the four abstention gates, each with the reason it fired
  * discordance flags — isolates where clinical lookup would give the dangerous wrong answer
  * per-drug rule-vs-model comparison, so every claim is stated against the alternative
  * the six-tier validation, so the interface can show honest numbers rather than the
    optimistic ones

    python3 pipeline/export_ui.py

Writes ui/predictions.json and ui/predictions.js
"""

import json
import os
import sys

import numpy as np
import shap
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, HERE, build_vocab, cohort, load_ncbi, matrix  # noqa: E402
from firewall import Firewall  # noqa: E402
from rules import RULES, coverage_ok  # noqa: E402

DRUGS = ["meropenem", "ertapenem", "ciprofloxacin", "levofloxacin", "ceftazidime",
         "ceftriaxone", "gentamicin", "amikacin", "trimethoprim-sulfamethoxazole",
         "piperacillin-tazobactam"]
N_DEMO = 16

# Human-readable descriptions for canonical tokens. Clinician-facing, so written for a doctor
# at 3 a.m. rather than a bioinformatician.
NOTES = {
    "blakpc": ("KPC carbapenemase", "Enzymatic degradation",
               "Class A carbapenemase. Hydrolyses last-resort carbapenems. Plasmid-borne and "
               "associated with the ST258 global outbreak clone."),
    "blandm": ("NDM metallo-beta-lactamase", "Enzymatic degradation",
               "Zinc-dependent enzyme. Not inhibited by standard beta-lactamase inhibitors, "
               "which removes most rescue options."),
    "blaoxa-48": ("OXA-48 carbapenemase", "Enzymatic degradation",
                  "Hydrolyses carbapenems weakly, so it is easily missed on routine testing."),
    "blactx-m": ("CTX-M extended-spectrum beta-lactamase", "Enzymatic degradation",
                 "The dominant ESBL worldwide. Defeats cephalosporins but NOT carbapenems."),
    "blashv": ("SHV beta-lactamase", "Enzymatic degradation",
               "Chromosomal in Klebsiella and present in ~92% of isolates, so its presence "
               "alone says little."),
    "blatem": ("TEM beta-lactamase", "Enzymatic degradation",
               "Broad-spectrum penicillinase. Usually not carbapenem-relevant."),
    "POINT:gyra": ("gyrA target mutation", "Target modification",
                   "Alters DNA gyrase so fluoroquinolones no longer bind. The primary driver of "
                   "ciprofloxacin resistance — and invisible to any gene-presence lookup."),
    "POINT:parc": ("parC target mutation", "Target modification",
                   "Second-step topoisomerase mutation. Combined with gyrA it produces high-level "
                   "fluoroquinolone resistance."),
    "TRUNC:ompk35": ("OmpK35 porin loss", "Reduced permeability",
                     "Loss of the outer-membrane channel the drug enters through. Raises "
                     "carbapenem MICs when combined with a beta-lactamase."),
    "TRUNC:ompk36": ("OmpK36 porin loss", "Reduced permeability",
                     "As OmpK35. Porin loss explains carbapenem resistance in isolates with no "
                     "carbapenemase at all."),
    "TRUNC:mgrb": ("mgrB disruption", "Regulatory loss",
                   "The main colistin-resistance mechanism in Klebsiella. Not an acquired gene, "
                   "so gene-based tools miss it entirely."),
    "aac(3)": ("AAC(3) aminoglycoside acetyltransferase", "Drug modification",
               "Inactivates gentamicin. A genuinely portable mechanism that travels on plasmids "
               "across unrelated lineages."),
    "aac(6')": ("AAC(6') aminoglycoside acetyltransferase", "Drug modification",
                "Substrate range varies by variant; the -Ib-cr form also modifies "
                "fluoroquinolones."),
    "qnrb": ("QnrB quinolone-protection protein", "Target protection",
             "Shields DNA gyrase. Low-level resistance alone, but lowers the bar for full "
             "resistance to emerge during treatment."),
    "sul": ("Sul dihydropteroate synthase", "Target replacement",
            "An alternative version of the enzyme the drug is designed to block."),
    "oqxab": ("OqxAB efflux pump", "Efflux",
              "Chromosomal in Klebsiella. Pumps fluoroquinolones out; near-universal, so it "
              "predicts little on its own."),
}


def describe(tok):
    if tok in NOTES:
        n = NOTES[tok]
        return dict(gene=n[0], mechanism=n[1], clinical=n[2])
    if tok.startswith("POINT:"):
        return dict(gene=f"{tok[6:]} target mutation", mechanism="Target modification",
                    clinical="A chromosomal mutation. Gene-presence tools cannot represent this.")
    if tok.startswith("TRUNC:"):
        return dict(gene=f"{tok[6:]} loss", mechanism="Gene disruption",
                    clinical="Loss of function in a chromosomal gene.")
    return dict(gene=tok, mechanism=None,
                clinical="No curated description. The model uses this as a statistical marker; "
                         "treat it as association rather than mechanism.")


def main():
    feats, labels, meta = load_ncbi("klebsiella")
    split = json.load(open(os.path.join(DATA, "split_v2.json")))
    train_ids, hold_ids = split["train"], split["holdout"]
    known = {t for g in train_ids for t in feats.get(g, ())}
    print(f"train {len(train_ids)} · holdout {len(hold_ids)}")

    models = {}
    for drug in DRUGS:
        ids, y = cohort({g: feats[g] for g in train_ids}, labels, drug,
                        min_n=150, min_minority=30)
        if ids is None:
            continue
        vocab = build_vocab(feats, ids)
        if len(vocab) < 3:
            continue
        X = matrix(feats, ids, vocab)
        mdl = CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=250,
                                                                    random_state=0),
                                     method="isotonic", cv=3).fit(X, y)
        raw = HistGradientBoostingClassifier(max_iter=250, random_state=0).fit(X, y)
        models[drug] = dict(fw=Firewall(mdl, vocab, X, y, known), raw=raw, vocab=vocab,
                            explainer=shap.TreeExplainer(raw))
        print(f"   {drug:<32} n={len(ids):>4}  features={len(vocab)}")

    # Score every quarantined isolate, then pick a demo set that shows the system's range.
    scored = []
    for g in hold_ids:
        if g not in feats:
            continue
        rec, n_res, n_ind, n_disc = [], 0, 0, 0
        for drug, m in models.items():
            a = m["fw"].assess(feats[g])
            truth = labels[g].get(drug)
            trig = RULES.get(drug, set())
            rule_fires = bool(feats[g] & trig)
            # Would clinical lookup give the dangerous wrong answer here?
            disc = (truth == 1 and not rule_fires)
            if disc:
                n_disc += 1
            if a["call"] == "RESISTANT":
                n_res += 1
            if a["call"] == "INDETERMINATE":
                n_ind += 1
            rec.append(dict(
                drug=drug, call=a["call"], probability=a["probability"],
                reason=a["reason"],
                truth=("Resistant" if truth == 1 else "Susceptible" if truth == 0 else None),
                rule_says=("Resistant" if rule_fires else "Susceptible") if trig else None,
                rule_wrong_and_dangerous=bool(disc),
                neighbour_resistance_rate=a["neighbour_resistance_rate"]))
        scored.append(dict(genome_id=g, meta=meta.get(g, {}),
                           n_determinants=len(feats[g]),
                           determinants=sorted(feats[g]),
                           drugs=rec, _res=n_res, _ind=n_ind, _disc=n_disc))

    # Prefer isolates that demonstrate something: a discordance, an abstention, and a drug that
    # still works. An all-resistant panel hides the clinical value, which is finding the survivor.
    def score(i):
        mixed = any(d["call"] == "SUSCEPTIBLE" for d in i["drugs"])
        return (-(i["_disc"] > 0), -(i["_ind"] > 0), -mixed, -i["_res"])
    demo = sorted(scored, key=score)[:N_DEMO]

    for iso in demo:
        for d in iso["drugs"]:
            m = models[d["drug"]]
            row = matrix(feats, [iso["genome_id"]], m["vocab"])
            sv = m["explainer"].shap_values(row)
            sv = (sv[..., 1] if sv.ndim == 3 else sv)[0]
            ev = []
            for j in np.argsort(-np.abs(sv))[:4]:
                if abs(sv[j]) < 0.05:
                    continue
                tok = m["vocab"][j]
                ev.append(dict(token=tok, contribution=round(float(sv[j]), 3),
                               present=bool(row[0][j]), **describe(tok)))
            d["evidence"] = ev
        for k in ("_res", "_ind", "_disc"):
            iso.pop(k, None)

    val = json.load(open(os.path.join(DATA, "validation_v2.json")))
    disc = json.load(open(os.path.join(DATA, "discordance.json")))
    defer = json.load(open(os.path.join(DATA, "deferral.json")))

    payload = dict(
        isolates=demo,
        validation=val["summary"],
        per_drug=val["per_drug"],
        discordance=disc["summary"],
        deferral=defer["summary"],
        provenance=dict(
            training="NCBI Pathogen Detection — AMRFinderPlus genotypes "
                     "(acquired genes, point mutations, truncations)",
            external="BV-BRC laboratory-confirmed phenotypes, gene presence only",
            organism="Klebsiella pneumoniae",
            train_isolates=len(train_ids), holdout_isolates=len(hold_ids),
            note="Predictions precomputed offline so the demo cannot fail live. "
                 "The pipeline runs for real in the tech video."))

    json.dump(payload, open(os.path.join(HERE, "ui", "predictions.json"), "w"), indent=1)
    with open(os.path.join(HERE, "ui", "predictions.js"), "w") as f:
        f.write("window.PREDICTIONS = " + json.dumps(payload) + ";\n")

    calls = [d["call"] for i in demo for d in i["drugs"]]
    print(f"\n{len(demo)} demo isolates · {len(models)} drugs")
    print(f"calls: R={calls.count('RESISTANT')} S={calls.count('SUSCEPTIBLE')} "
          f"IND={calls.count('INDETERMINATE')}")
    print(f"isolates showing a dangerous lookup failure: "
          f"{sum(1 for i in demo if any(d['rule_wrong_and_dangerous'] for d in i['drugs']))}")
    print("wrote ui/predictions.js")


if __name__ == "__main__":
    main()
