# Architecture & Methodology

Reference document for the system, why each part exists, and what it is measured to do.
Every number here is produced by a script in `pipeline/` and reproducible from a clean checkout.

---

## 1. What the system does

Given an assembled bacterial genome, it returns for each antibiotic: a call
(resistant / susceptible / **indeterminate**), a calibrated probability, the determinants driving
that call, and — where relevant — a flag that a standard genotype lookup would give the *wrong*
answer for this isolate.

The design commitment is that **a confidently wrong answer is worse than no answer.** Culture-based
susceptibility testing takes 48–72 hours; during that window clinicians prescribe empirically. A
tool that fills the gap with a confident mistake removes the caution that was protecting the
patient. So the system is built to refuse.

---

## 2. Data flow

```
NCBI Pathogen Detection ─┐
  AMRFinderPlus calls    │
  genes + POINT + TRUNC  ├─→ llm_harmonize.py ─→ vocab_map.json
                         │      (GPT-4o-mini)         │
BV-BRC ──────────────────┘                            ↓
  gene presence only                            features.py
  lab-confirmed phenotypes                    canonical tokens
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────┐
                    ↓                 ↓               ↓             ↓           ↓
              validate_v2.py    discordance.py   deferral.py   export_ui.py  rules.py
              6 tiers           lookup failures  abstention    demo payload  baseline
                    │                 │               │             │
                    └─────────────────┴───────────────┴─────────────┘
                                       ↓
                              ui/index.html (static)
```

The interface never calls a model. Predictions are precomputed and embedded so the demo loads
instantly and cannot fail during recording. The pipeline runs live in the tech video.

---

## 3. Component reference

| module | role |
|---|---|
| `acquire.py` | Paginated pull of BV-BRC AMR phenotypes, gene annotations and metadata |
| `ncbi_extract.py` | Parses NCBI Pathogen Detection into isolate → phenotypes + genotypes |
| `llm_harmonize.py` | Classifies every distinct annotation string into a canonical family |
| `harmonize.py` | Original regex mapper — retained for the coverage comparison |
| `features.py` | **Single source of truth** for feature construction |
| `rules.py` | ResFinder/PointFinder-style clinical baseline + coverage guard |
| `firewall.py` | The four abstention gates |
| `validate_v2.py` | Six-tier validation battery |
| `discordance.py` | Where lookup fails and whether we catch it |
| `deferral.py` | Deferral rate against the safety constraint |
| `edge_cases.py` / `eval_edges.py` | 93-case behavioural stress benchmark |
| `export_ui.py` | Builds the demo payload |

---

## 4. Feature representation

Three token types, all lowercase:

```
blakpc          acquired resistance gene, collapsed to family
POINT:gyra      target mutation, gene-level
TRUNC:ompk35    truncation / loss of function
```

**Families, not alleles.** `blaKPC-2` and `blaKPC-3` both become `blakpc`. Allele-level features
memorise; family-level features generalise. Measured: codon-level mutation encoding
(`gyrA_S83I`) scored −0.024 to +0.012 against gene-level — a wash, because sparsity costs more
than the resolution buys. Gene-level is used.

**Why mutations matter.** Gene presence alone cannot express the mechanisms driving resistance for
several major drug classes:

| drug class | actual mechanism | visible to gene lookup? |
|---|---|---|
| fluoroquinolones | *gyrA* / *parC* codon changes | no |
| colistin | *mgrB* / *pmrB* disruption | no (*mcr* is rare) |
| carbapenems | porin loss modulating a beta-lactamase | no |

Measured contribution of adding mutation features: ciprofloxacin +0.048, levofloxacin +0.060,
meropenem +0.030, cefepime +0.018, colistin +0.024. Every drug improved.

---

## 5. The LLM's role, and why it is there

The LLM does **not** make predictions. It performs annotation normalisation — a text
classification task with no training labels, where a model generalises and a rule cannot.

This was not a stylistic choice. The hand-written regex it replaced covered **24% of distinct
annotations** and was found, by auditing it, to silently discard `blaSHV`, `blaTEM` and `blaOXA`
through a word-boundary error (`\bSHV\b` does not match inside `blaSHV`), plus `oqxA`/`oqxB`
which were never encoded. Roughly 7,000 feature occurrences were being thrown away.

| | distinct annotations | annotation rows |
|---|---|---|
| regex | 52% | 23% |
| **LLM classifier** | **71%** | **52%** |

Each distinct string is classified once, cached, and gated on a confidence threshold of 0.5.
Cost is a few cents total and zero on re-runs.

**Why a gradient booster and not an LLM for the prediction itself:** the input is ~45 binary
features, not language; we have thousands of labelled examples, so supervised learning beats
zero-shot; we need calibrated probabilities and LLMs are poorly calibrated; and a clinical tool
must be deterministic. A zero-shot LLM asked "does blaKPC confer meropenem resistance" answers
from the same textbooks the lookup rule encodes — it would be a slower, less calibrated
reimplementation of the baseline we are trying to beat.

---

## 6. The four abstention gates

Applied in order. Each was added because measurement showed the previous set was insufficient.

**1. Confidence** — abstain inside an asymmetric band (0.35–0.65). Not centred on 0.5, because
calling a drug susceptible when it is resistant can kill, while the reverse wastes a last-resort
drug. These are a clinical judgement, not a tuned hyperparameter.

**2. Novelty** — abstain when the genome carries determinants absent from training. Originally
this fired only inside a middle probability band, which meant a prediction of 0.04 sailed through
even though that 0.04 was computed *without* the unrecognised protein. It now blocks a
**susceptible** call at any confidence, and does not block a resistant call, which is already the
cautious side. This single change took the novel-mechanism benchmark from **0/12 to 12/12**.

**3. Completeness** — abstain when the genome carries implausibly few determinants. Across 7,276
real genomes only 4 carry zero and the median is 13, so a near-empty vector signals a truncated
assembly rather than a clean organism. Took degraded-assembly cases from 65% to **95%**.

**4. Coherence** — abstain when the prediction contradicts the isolate's own resistance profile,
measured against its nearest training neighbours by Jaccard similarity.

---

## 7. Validation methodology

Six tiers, each removing a different crutch. A model that holds up only on the first is doing
recall, not biology.

| tier | mean AUC | what it removes |
|---|---|---|
| 1. random split | 0.895 | nothing — the optimistic baseline |
| 2. clone-aware | 0.876 | identical genotype profiles straddling the split |
| 3. locked holdout | 0.895 | quarantined before modelling, used once |
| 4. **external** | **0.851** | different curation **and** no mutation features |
| 5. temporal | 0.792 | trained on the past, tested on the future |
| 6. geographic | 0.799 | trained on some countries, tested on others |

The external tier trains on NCBI (with mutations) and tests on BV-BRC (gene presence only), so it
measures cross-curation transfer and feature degradation simultaneously. It is the number we
consider load-bearing.

### Against the clinical baseline

Model **0.837** vs rule **0.777** balanced accuracy — **+0.060**, winning 13 drugs, tying 7,
losing 2.

---

## 8. Baseline specification — and three strawmen we caught

A baseline you have accidentally crippled flatters you and will not survive review. This happened
three times in this project and each is recorded in `rules.py`:

| determinant | prevalence in *K. pneumoniae* | consequence |
|---|---|---|
| `blaSHV` | **92%** — chromosomal | cephalosporin rule fired on nearly every isolate, scored 0.49, inflated our apparent gain from +0.047 to **+0.165** |
| `oqxAB` | **98%** — chromosomal | fluoroquinolone rule fired on 98% of isolates |
| `nfsA`/`nfsB` | not called in this dataset | nitrofurantoin rule could never fire; 75% "rule wrong" was meaningless |

**The general principle: a chromosomal determinant of a species is not evidence of resistance in
that species.** Only acquired or mutated ones are.

`rules.coverage_ok()` now rejects any rule firing below 5% or above 95% automatically, rather than
relying on someone noticing.

---

## 9. Where clinical lookup fails — the headline result

Across 20 antibiotics with a valid rule baseline:

- **2,111** isolates where lookup reports susceptible and the isolate is genuinely **resistant**
- **1,380** of those (**65%**) correctly called resistant by this system
- **842** where lookup discards a drug that would have worked

Mechanisms responsible for the dangerous misses:

| mechanism | share |
|---|---|
| efflux / regulator | 52% |
| target mutation | 33% |
| porin loss | 14% |

This is the argument for the system: not that it is more accurate on average, but that it sees the
mechanisms current practice structurally cannot.

---

## 10. What abstention buys

| | |
|---|---|
| deferral rate | **19%** (was 72% before the feature rebuild) |
| accuracy on answered cases | 0.903 |
| accuracy if forced to answer everything | 0.839 |
| **gain from knowing when to stop** | **+0.064** |
| lethal errors | 80 / 2,626 predictions (3.0%) |

The 72% figure was a vocabulary artifact — NCBI tokens absent from a BV-BRC-trained vocabulary
tripped the novelty gate on a schema difference rather than genuine novelty. Training and
predicting through one shared vocabulary removed it.

---

## 11. Stress benchmark

`data/edge_cases.json` — 93 cases across 10 categories, built by perturbing real quarantined
isolates. Graded against expected *behaviour*, because for several categories the correct answer
is a refusal rather than a label.

Iterative hardening: **72% pass / 21 lethal errors → 85% pass / 3 lethal errors.**

---

## 12. Known limitations

- *Klebsiella pneumoniae* only. E. coli, S. aureus and A. baumannii are acquired but unused.
- `invisible_mechanism` remains unsolved: when every trace of a determinant is deleted, the
  information is genuinely gone and no gate recovers it. Measured neighbour resistance rates for
  those cases run 0.00–0.44 — they genuinely resemble susceptible genomes.
- **Colistin loses to the rule** (−0.064) and is not recommended for use.
- 3 lethal errors remain in the stress benchmark; 80 across the deferral evaluation.
- Clone grouping uses exact genotype-profile identity as a proxy; NCBI publishes no MLST here, so
  this is conservative and will not catch all relatedness.
- Gene presence is not gene expression. We observed 387 gene/phenotype discordances across 324 of
  683 holdout isolates — nearly half carry a determinant for a drug that still works.
- Not a medical device. Every treatment decision stays with a qualified clinician.

---

## 13. Reproduce

```bash
pip3 install pandas scikit-learn shap openai
python3 pipeline/acquire.py 573 562     # BV-BRC
python3 pipeline/ncbi_extract.py        # NCBI external set
python3 pipeline/llm_harmonize.py       # annotation normalisation (needs OPENAI_API_KEY)
python3 pipeline/validate_v2.py         # six-tier battery
python3 pipeline/discordance.py         # lookup failure analysis
python3 pipeline/deferral.py            # abstention measurement
python3 pipeline/export_ui.py           # demo payload
open ui/index.html
```
