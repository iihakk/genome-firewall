# Verification report

Rebuild of the evidence base after the prototype was judged too thin. Every number below is
measured by scripts in `pipeline/`, reproducible from a clean checkout.

---

## 1. What changed in scale

| | prototype | now |
|---|---|---|
| Klebsiella genomes | 600 | **7,276** |
| genomes with usable labels | ~220/drug | **5,751** |
| antibiotics validated | 6 | **24** |
| meropenem training genomes | 218 | **3,576** |
| feature source | BV-BRC only | **BV-BRC + NCBI/AMRFinderPlus, harmonized** |
| validation | repeated `train_test_split` | **5 independent tiers + 93-case stress benchmark** |

Also acquired for cross-species work: *E. coli* (12,627 genomes), *S. aureus*, *A. baumannii*.

## 2. Datasets

**BV-BRC** — primary training source. 85,291 laboratory-confirmed AMR records across 7,276
genomes. Filtered to `evidence = "Laboratory Method"`; the other ~16M records in the table are
another model's predictions and training on them teaches imitation, not biology.

**NCBI Pathogen Detection** (`PDG000000012.2470`) — external validation. 167,247 isolates, of which
**2,612 carry AST phenotypes**. Independent curation, independent submitters, and crucially an
independent gene caller: `AMR_genotypes` comes from **AMRFinderPlus**, the tool the challenge brief
names as its default. It is also richer than BV-BRC's gene lists, carrying mechanisms a
presence/absence vector cannot express:

```
gyrA_S83I=POINT        target mutation — fluoroquinolone resistance
ompK35_E42RfsTer       porin truncation — a genuine carbapenem mechanism
```

**Overlap was measured, not assumed.** 50 isolates shared an assembly accession and 355 shared an
SRA run with BV-BRC. All were removed, leaving **1,597 genuinely unseen isolates**.

**CARD / ResFinder** — reference vocabularies consulted when building the harmonization rules.

## 3. Harmonization

The two sources describe the same enzyme differently — BV-BRC writes
`Class A beta-lactamase (EC 3.5.2.6) => KPC family, carbapenem-hydrolyzing`, NCBI writes
`blaKPC-2`. `pipeline/harmonize.py` maps both into **50 canonical resistance tokens**.

Alleles deliberately collapse to families: `blaKPC-2` and `blaKPC-3` both become `blaKPC`.
Allele-level features memorise; family-level features generalise. Non-resistance annotations that
the prototype was leaning on — `Chromosome (plasmid) partitioning protein ParA` — are dropped.

## 4. Five-tier validation

Each tier removes a different crutch. Mean AUC across 24 antibiotics:

| tier | mean AUC | what it removes |
|---|---|---|
| 1. random split | **0.936** | nothing — the optimistic baseline most work reports |
| 2. lineage-aware | **0.892** | relatives in both train and test (MLST grouping) |
| 3. locked holdout | **0.904** | 683 genomes quarantined before modelling, used once |
| 4. **external (NCBI)** | **0.797** | same source, same curation, same gene caller |
| 5. temporal | **0.845** | trained ≤2014, tested on later isolates |

**The external result is the headline.** Moving to an independent source costs **−0.139 AUC** —
six times the lineage effect. Any single-source evaluation, however carefully split, overstates
what the model will do on data it did not grow up with.

### Not every drug survives — and that decides what ships

| drug | external AUC | verdict |
|---|---|---|
| cefotaxime | 0.984 | ship |
| tobramycin | 0.975 | ship |
| cefuroxime | 0.961 | ship |
| aztreonam | 0.943 | ship |
| ceftazidime | 0.928 | ship |
| meropenem | 0.707 | ship with caution |
| cefoxitin | 0.629 | **do not ship** |
| imipenem | 0.592 | **do not ship** |
| amikacin | 0.549 | **do not ship** |
| **colistin** | **0.446** | **do not ship — worse than chance** |

Colistin resistance is driven by *mcr* genes and chromosomal *pmrB*/*phoQ*/*mgrB* mutations that a
gene-presence vector cannot represent. The model is not merely weak there, it is anti-correlated.
Shipping it would be actively harmful. Imipenem and meropenem are both carbapenems yet differ by
0.115 externally, which is itself a warning against assuming within-class transfer.

## 5. Edge-case benchmark

`data/edge_cases.json` — **93 cases, 10 categories**, derived by perturbing real quarantined
isolates rather than inventing genomes. Deterministic, seed 20260719.

For several categories the correct answer is **not a label but a refusal**, so cases are graded
against an `expected_behaviour` contract rather than accuracy.

| category | n | what it tests |
|---|---|---|
| novel_mechanism | 12 | carbapenemase replaced by an unrecognised protein call |
| invisible_mechanism | 8 | determinant deleted outright — a documented hard limit |
| degraded_assembly | 20 | 40% and 70% of gene calls dropped |
| silent_gene | 10 | determinant present, isolate still susceptible |
| point_only | 10 | resistance with no acquired gene (target mutation) |
| clean_background | 10 | mechanism with no co-carried genes to lean on |
| conflicting | 8 | carbapenemase with a susceptible-looking profile |
| chimeric | 3 | two isolates merged — contaminated sample |
| minimal / bare | 12 | one determinant / none at all |

**A finding from building it:** 387 gene/phenotype discordances across 324 of 683 holdout isolates.
Nearly half carry a resistance gene for a drug they still test susceptible to. Gene lookup alone is
not a substitute for a calibrated model.

## 6. Hardening driven by the benchmark

The benchmark's first run was a failure, and fixing it is the actual engineering story.

| run | gates | pass | lethal errors |
|---|---|---|---|
| initial | confidence only | 72% | **21** |
| + coherence | 3 gates | 76% | 13 |
| **+ novelty-blocks-susceptible, + completeness** | **4 gates** | **85%** | **3** |

*Lethal error* = a confident SUSCEPTIBLE on a genuinely resistant genome — the call that puts a
patient on a drug that does nothing.

**What each fix came from:**

- **Coherence gate.** 12 novel-mechanism cases produced 12 confident susceptible calls. Novelty
  detection could not help because deleting a gene makes a genome look *ordinary*, not unfamiliar.
  So the system now checks its prediction against what the isolate's nearest training neighbours
  actually did.
- **Novelty blocks susceptible at any confidence.** The gate originally fired only in a middle
  probability band, so a prediction of 0.04 sailed through — even though that 0.04 was computed
  without the unrecognised protein. Unknown machinery now blocks a susceptible call outright. It
  does not block a resistant call, which is already the cautious side. This alone took
  novel_mechanism from 0/12 to **12/12**.
- **Completeness gate.** An unusually sparse genome is more likely a truncated assembly than a
  clean isolate. Took degraded_assembly from 65% to **95%**.

### One expectation was revised, and why

The `bare` category originally expected a confident SUSCEPTIBLE on a genome stripped of all
determinants. The model abstained instead, which prompted a check: across 7,276 real genomes only
**4** carry zero determinants, and the median is 13. Chromosomal SHV and fosA are near-universal in
this species, so an empty vector is an annotation failure, not a pristine organism — and it is
indistinguishable from a genome carrying an unrecognised mechanism. **Abstention is correct and the
original expectation was wrong.** Revised on the distribution, and flagged here because changing a
test after seeing results deserves to be visible rather than quiet.

## 7. Honest limits

- **invisible_mechanism is unscored and unsolved.** When every trace of a determinant is absent,
  the information is genuinely gone; measured neighbour resistance rates for those cases run
  0.00–0.44, meaning they really do resemble susceptible genomes. No gate recovers this. It needs
  richer features — point mutations, plasmid context, raw sequence.
- 3 lethal errors remain, in `degraded_assembly` and `point_only`.
- `chimeric` sits at 1/3; mixed-sample detection is weak.
- Temporal test uses a 2014 cut because collection dates cluster in 2012–2015; only 28 genomes
  postdate 2018.
- Klebsiella only. Cross-species transfer to the acquired *E. coli* set is not yet measured.

## Reproduce

```bash
python3 pipeline/acquire.py 573 562      # BV-BRC, ~6 min
python3 pipeline/ncbi_extract.py         # NCBI external set
python3 pipeline/validate.py             # 5-tier battery, ~18 min
python3 pipeline/edge_cases.py           # regenerate benchmark
python3 pipeline/eval_edges.py           # grade the firewall
```

Outputs: `validation_report.json`, `edge_cases.json`, `edge_case_results.json`, `split.json`.
