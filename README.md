# Genome Firewall

**Predicting antibiotic resistance from a bacterial genome — and refusing to guess when it shouldn't.**

Hack-Nation 6th Global AI Hackathon · Challenge 6 · *Klebsiella pneumoniae*

---

## The problem

Culture-based susceptibility testing takes **48–72 hours**. For those two to three days the doctor
is guessing. Guess too narrow and the infection advances untreated; in bloodstream infection,
delayed effective therapy drives mortality. Guess too broad and last-resort drugs are burned,
accelerating the resistance that caused the problem. AMR is associated with **4.7 million deaths**
a year.

Sequencing takes hours. So the genome can answer, days before the culture does.

## The headline result

A ResFinder/PointFinder-style genotype lookup is what a laboratory can run today. Across 20
antibiotics:

> **2,111 isolates where lookup reports the drug will work — and it will not.
> This system correctly identifies 1,380 of them (65%).**

A further **842** isolates have a usable antibiotic discarded by lookup.

Why lookup misses them — mechanisms a gene-presence rule cannot express:

| mechanism | share of dangerous misses |
|---|---|
| efflux / regulator | 52% |
| target mutation | 33% |
| porin loss | 14% |

This is the argument for the system: not that it is more accurate on average, but that it sees
mechanisms current practice is structurally blind to.

## Why it is a firewall, not a classifier

A classifier is forced to answer. Show it a genome carrying a mechanism it was never taught and
the determinant checklist comes back clean — indistinguishable from genuine susceptibility — and
it returns **"susceptible", confidently**. The doctor prescribes a drug that does nothing, and the
confident wrong answer has removed the caution that was protecting the patient.

So the system asks a second question first — *have I seen anything like this?* — and refuses when
the answer is no.

| | |
|---|---|
| deferral rate | **19%** |
| accuracy on answered cases | 0.903 |
| accuracy if forced to answer everything | 0.839 |
| **bought by knowing when to stop** | **+0.064** |

## Validation

Six tiers, each removing a different crutch:

| tier | mean AUC |
|---|---|
| random split (optimistic) | 0.895 |
| clone-aware | 0.876 |
| locked holdout | 0.895 |
| **external** (different curation, no mutation features) | **0.851** |
| temporal | 0.792 |
| geographic | 0.799 |

Against the clinical rule: **0.837 vs 0.777** balanced accuracy
(**+0.06**), winning 13 drugs, tying 7, losing 2.

## What we tested that failed

**Protein language-model embeddings.** Held out all 30 carbapenemases: 100% were still recognised
as beta-lactam machinery, but **0% as carbapenem-hydrolyzing** — the distinction that decides
whether the last-resort drug works. Claim dropped; embeddings kept only for novelty detection.

**Cross-species transfer.** Trained on Klebsiella, tested on E. coli: we score 0.768, the
species-agnostic rule scores 0.874. **The model does not transfer and should not be deployed
cross-species.** Colistin scores exactly 0.500 there, independently confirming its exclusion.

**Three strawman baselines, caught on ourselves.** `blaSHV` is chromosomal in Klebsiella (92% of
isolates); including it made the rule fire on nearly every genome, score 0.49, and inflated our
apparent gain from +0.047 to +0.165. Same with `oqxAB` at 98%. There is now an automatic guard
rejecting any rule firing below 5% or above 95%.

Full detail in [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`VALIDATION_FINDINGS.md`](VALIDATION_FINDINGS.md).

## Data

**NCBI Pathogen Detection** — primary training source. AMRFinderPlus genotypes carrying acquired
genes **plus point mutations and truncations**, the mechanisms gene-presence tools cannot see.

**BV-BRC** — external validation, 7,273 genomes, gene presence only. Filtered to
`evidence = "Laboratory Method"`; the other ~16M records are another model's predictions.

## Run it

```bash
pip3 install pandas scikit-learn shap openai
python3 pipeline/acquire.py 573 562
python3 pipeline/ncbi_extract.py
python3 pipeline/llm_harmonize.py      # needs OPENAI_API_KEY
python3 pipeline/validate_v2.py
python3 pipeline/discordance.py
python3 pipeline/export_ui.py
open ui/index.html
```

## Honest limitations

- ***Klebsiella pneumoniae* only** — measured, not assumed. See cross-species above.
- **Colistin excluded**: loses to the rule and scores at chance cross-species.
- 80 confident-susceptible errors remain across 2,626 predictions.
- `invisible_mechanism` unsolved: when every trace of a determinant is deleted, the information is
  genuinely gone and no gate recovers it.
- Gene presence is not gene expression — 387 gene/phenotype discordances observed across 324 of
  683 holdout isolates.
- Not a medical device. Every treatment decision stays with a qualified clinician.
