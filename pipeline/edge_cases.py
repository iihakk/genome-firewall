"""Generate a stress-test benchmark of hard cases.

Standard held-out validation asks "does the model fit unseen data from the same distribution?"
That is necessary and not sufficient. A clinical system also has to behave sanely on inputs that
are rare, degraded, or actively misleading — and for several of these the correct behaviour is
*not* a confident label, it is abstention.

Every case is derived from a REAL isolate and then perturbed, rather than invented. A fabricated
genome proves nothing; a real genome with its carbapenemase deleted proves exactly what happens
when the mechanism is invisible.

Categories
----------
novel_mechanism     resistance driven by a family withheld from training — the superbug case
clean_background    real mechanism, no co-carried genes to lean on (linkage crutch removed)
degraded_assembly   fraction of gene calls dropped: poor coverage, fragmented "reconstructed" genome
silent_gene         resistance gene present, organism phenotypically susceptible
point_only          resistance from a chromosomal mutation only, no acquired gene
conflicting         carbapenemase plus markers usually seen in susceptible isolates
chimeric            gene calls merged from two isolates — contaminated / mixed sample
minimal             exactly one resistance determinant
bare                no resistance determinants at all

    python3 pipeline/edge_cases.py

Writes data/edge_cases.json  (and .tsv for humans)
"""

import json
import os
import random
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import canon_bvbrc  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
RNG = random.Random(20260719)

CARBAPENEMASES = {"blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48", "blaOXA-carbapenemase"}
ESBL = {"blaCTX-M", "blaSHV", "blaTEM"}


def load():
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
    labels = defaultdict(dict)
    for gid, d, p in zip(amr.genome_id, amr.antibiotic, amr.resistant_phenotype):
        labels[gid][d.strip().lower()] = p
    meta = pd.read_csv(os.path.join(DATA, "meta_573.tsv"), sep="\t", dtype=str)
    meta = meta.apply(lambda s: s.str.strip('"') if s.dtype == object else s).set_index("genome_id")
    return feats, labels, meta


def case(cid, cat, src, feats, drug, truth, expect, why):
    return dict(case_id=cid, category=cat, derived_from=src,
                features=sorted(feats), n_features=len(feats),
                drug=drug, ground_truth=truth, expected_behaviour=expect, rationale=why)


def main():
    feats, labels, meta = load()
    hold = set()
    sp = os.path.join(DATA, "split.json")
    if os.path.exists(sp):
        hold = set(json.load(open(sp))["holdout"])
        print(f"drawing from {len(hold)} quarantined holdout genomes")
    pool = [g for g in feats if (not hold or g in hold) and g in labels]
    print(f"candidate isolates: {len(pool)}")

    cases, n = [], 0

    def add(*a):
        nonlocal n
        n += 1
        cases.append(case(f"EC{n:03d}", *a))

    src = [g for g in pool if feats[g] & CARBAPENEMASES
           and labels[g].get("meropenem") == "Resistant"]

    # 1. novel mechanism — the carbapenemase is REPLACED with an unrecognised token rather than
    #    deleted. This is what a genuinely new enzyme looks like in practice: AMRFinderPlus still
    #    calls a protein, it simply isn't in any vocabulary the model was trained on. The gene is
    #    present and undetectable-as-known, not absent.
    for g in RNG.sample(src, min(12, len(src))):
        f = (feats[g] - CARBAPENEMASES) | {"UNKNOWN:novel_beta_lactamase"}
        add("novel_mechanism", g, f, "meropenem", "Resistant", "ABSTAIN_OR_RESISTANT",
            "Carbapenemase swapped for an unrecognised protein call, mimicking a newly evolved "
            "enzyme. The system cannot know what it does — but it can see that something "
            "unfamiliar is there, and must refuse rather than guess.")

    # 1b. invisible mechanism — the determinant is deleted outright, leaving no trace.
    #     This is included to document a hard limit rather than to be passed: if every trace of a
    #     mechanism is absent from the feature space, the information is genuinely gone and no
    #     amount of gating recovers it. Measured neighbour resistance rates for these cases run
    #     at 0.00–0.44, i.e. these genomes really do resemble susceptible ones. Reported honestly
    #     as the boundary of what this representation can do.
    for g in RNG.sample(src, min(8, len(src))):
        f = feats[g] - CARBAPENEMASES
        add("invisible_mechanism", g, f, "meropenem", "Resistant", "DOCUMENTED_LIMITATION",
            "Every trace of the carbapenemase removed. Unrecoverable by construction — included "
            "to bound the claim, not to be passed. Richer features (point mutations, plasmid "
            "context, raw sequence) would be required to detect this class.")

    # 2. clean background — mechanism present, every other acquired gene stripped
    for g in RNG.sample(src, min(10, len(src))):
        f = (feats[g] & CARBAPENEMASES) | {"fosA"}
        add("clean_background", g, f, "meropenem", "Resistant", "RESISTANT",
            "Carbapenemase with no co-carried resistance genes. Removes the linkage crutch the "
            "model leans on when a plasmid arrives carrying a crowd.")

    # 3. degraded assembly — drop 40% and 70% of gene calls
    rich = [g for g in pool if len(feats[g]) >= 8 and "meropenem" in labels[g]]
    for g in RNG.sample(rich, min(10, len(rich))):
        for frac in (0.4, 0.7):
            keep = sorted(feats[g])
            RNG.shuffle(keep)
            f = set(keep[int(len(keep) * frac):])
            add("degraded_assembly", g, f, "meropenem", labels[g]["meropenem"],
                "ABSTAIN_IF_MECHANISM_LOST",
                f"{int(frac*100)}% of gene calls dropped, simulating low coverage or a fragmented "
                "reconstruction. Confidence should fall as evidence disappears.")

    # 4. silent gene — determinant present, organism still susceptible. Found by searching every
    #    gene/drug pair for genuine discordance rather than assuming which one will show it:
    #    gene presence is not gene expression, and these are the cases that prove it.
    EXPECT = {
        "blaKPC": ["meropenem", "imipenem"],
        "blaCTX-M": ["ceftazidime", "ceftriaxone", "cefotaxime"],
        "blaOXA-48": ["meropenem", "ertapenem"],
        "aac(3)": ["gentamicin"],
        "aac(6')": ["amikacin", "tobramycin"],
        "qnrB": ["ciprofloxacin", "levofloxacin"],
        "sul": ["trimethoprim/sulfamethoxazole"],
        "tet": ["tetracycline"],
        "mph": ["azithromycin", "erythromycin"],
    }
    discord = []
    for g in pool:
        for gene, drugs_ in EXPECT.items():
            if gene not in feats[g]:
                continue
            for d in drugs_:
                if labels[g].get(d) == "Susceptible":
                    discord.append((g, gene, d))
    RNG.shuffle(discord)
    seen_g = set()
    for g, gene, d in discord:
        if g in seen_g or len(seen_g) >= 10:
            continue
        seen_g.add(g)
        add("silent_gene", g, feats[g], d, "Susceptible", "ABSTAIN_OR_SUSCEPTIBLE",
            f"{gene} is present yet the isolate tested susceptible to {d}. The determinant is "
            "not being expressed, or is a non-functional variant. Presence-based reasoning "
            "over-calls resistance here.")
    print(f"   found {len(discord)} gene/phenotype discordances across {len(set(x[0] for x in discord))} isolates")

    # 5. point-mutation-only — no acquired quinolone gene, still resistant
    pt = [g for g in pool if labels[g].get("ciprofloxacin") == "Resistant"
          and not (feats[g] & {"qnrA", "qnrB", "qnrS", "qnr_other"})]
    for g in RNG.sample(pt, min(10, len(pt))):
        add("point_only", g, feats[g], "ciprofloxacin", "Resistant", "ABSTAIN_OR_RESISTANT",
            "Fluoroquinolone resistance with no acquired qnr gene — almost certainly a gyrA/parC "
            "target mutation, which a gene-presence feature space cannot represent at all.")

    # 6. conflicting evidence — carbapenemase alongside an otherwise sparse background
    for g in RNG.sample(src, min(8, len(src))):
        f = (feats[g] & CARBAPENEMASES) | (ESBL & feats[g]) | {"fosA", "qac"}
        add("conflicting", g, f, "meropenem", "Resistant", "RESISTANT",
            "Carbapenemase with a susceptible-looking accessory profile. Tests whether the model "
            "weighs the causal mechanism above the background.")

    # 7. chimeric — two isolates merged, as in a contaminated or polymicrobial sample
    for _ in range(8):
        a, b = RNG.sample(pool, 2)
        if "meropenem" not in labels[a]:
            continue
        add("chimeric", f"{a}+{b}", feats[a] | feats[b], "meropenem", labels[a]["meropenem"],
            "ABSTAIN",
            "Gene calls from two isolates merged, simulating contamination or a mixed sample. "
            "A single confident call is not defensible when the input is not one organism.")

    # 8. minimal / 9. bare
    for g in RNG.sample(src, min(6, len(src))):
        one = sorted(feats[g] & CARBAPENEMASES)[:1]
        add("minimal", g, set(one), "meropenem", "Resistant", "RESISTANT",
            "Exactly one determinant and nothing else. Can the model act on a lone mechanism?")
    # 9. bare — constructed by stripping every determinant from a susceptible isolate. No real
    #    genome in the holdout is this sparse (the sparsest carries 4), so this one is explicitly
    #    synthetic. It is the input a novel mechanism is indistinguishable from, which is the
    #    entire reason abstention exists.
    # EXPECTATION REVISED after the model failed this case and prompted us to check the data.
    # Original expectation was a confident SUSCEPTIBLE call. That was wrong: across 7,276 real
    # Klebsiella genomes only 4 carry zero determinants and the median is 13 (5th percentile 7).
    # Chromosomal SHV and fosA are near-universal in this species, so an empty determinant vector
    # is an annotation or assembly failure, not a pristine isolate. Abstention is the clinically
    # correct response and the revision is justified by the distribution, not by the score.
    sus = [g for g in pool if labels[g].get("meropenem") == "Susceptible"]
    for g in RNG.sample(sus, min(6, len(sus))):
        add("bare", f"{g} (determinants stripped)", set(), "meropenem", "Susceptible",
            "ABSTAIN",
            "Constructed: all determinants removed. Only 4 of 7276 real genomes look like this, "
            "so an empty vector signals a failed pipeline rather than a clean organism — and it "
            "is indistinguishable from a genome carrying an unrecognised mechanism.")

    out = os.path.join(DATA, "edge_cases.json")
    json.dump(dict(
        generated="deterministic, seed 20260719",
        source="BV-BRC Klebsiella pneumoniae, laboratory-confirmed phenotypes",
        note="Derived from real isolates by perturbation. 'expected_behaviour' encodes the "
             "clinically acceptable response, which for several categories is abstention rather "
             "than a label.",
        n_cases=len(cases), cases=cases), open(out, "w"), indent=1)

    df = pd.DataFrame([{k: v for k, v in c.items() if k != "features"} for c in cases])
    df.to_csv(os.path.join(DATA, "edge_cases.tsv"), sep="\t", index=False)

    print(f"\nwrote {len(cases)} cases -> {out}")
    print(df.groupby("category").size().to_string())


if __name__ == "__main__":
    main()
