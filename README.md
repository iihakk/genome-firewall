# Genome Firewall

**Predicting antibiotic resistance from a bacterial genome — and refusing to guess when it shouldn't.**

Hack-Nation 6th Global AI Hackathon · Challenge 6 · Klebsiella pneumoniae

---

## The problem

A patient has a serious bacterial infection. Culture-based susceptibility testing takes **48–72
hours** — the bacteria must be grown against each antibiotic and watched. For those two to three
days the doctor is guessing. Guess too narrow and the infection advances unchecked; in bloodstream
infection, delay in effective therapy drives mortality sharply. Guess too broad and you burn
last-resort drugs, accelerating the resistance that created the problem.

Sequencing takes hours. So the genome can answer, days before the culture does.

## What this does

Given an assembled bacterial genome, for each antibiotic it returns:

- a **call** — resistant, susceptible, or *indeterminate*
- a **calibrated probability** — when it says 0.85 it is right about 85% of the time
- an **evidence panel** — which resistance genes drove the call, what each one does clinically,
  and which are merely passengers riding the same plasmid

## Why it is a firewall, not a classifier

A classifier is forced to answer. Show it a genome carrying a resistance mechanism it was never
taught and the gene checklist comes back clean — indistinguishable from genuine susceptibility. It
returns **"susceptible", with high confidence**. The doctor prescribes a drug that does nothing,
and the confident wrong answer has removed the caution that would otherwise have protected the
patient. A confidently wrong model is more dangerous than no model.

So this system asks a second question first — *have I seen anything like this before?* — and when
the answer is no, it says so and defers to the laboratory. **Its value is not a better prediction.
It is knowing when not to make one.**

The two errors are not symmetric: calling a drug susceptible when it is resistant can kill;
calling it resistant when it is susceptible wastes a last-resort drug. The abstention thresholds
in `pipeline/build.py` are asymmetric by design and are a clinical judgement, not a hyperparameter.

## The finding: most reported accuracy in this field is inflated

We measured performance inflation at **two independent levels**, on real data.

| Level | Naive split | Honest split | Inflation |
|---|---|---|---|
| **Genome** — bacterial lineage (MLST) | 0.915 AUC | **0.892 AUC** | +0.024 |
| **Protein** — sequence family | 0.955 acc | **0.451 acc** | **+0.504** |

Bacterial genomes are related by descent, and resistance proteins come in families of
near-identical variants (KPC-2, KPC-3, KPC-18…). Split either at random and near-copies land in
both training and test, so the model scores by recognising something it has effectively already
seen. Group by lineage and by protein family instead, and the numbers fall.

The genome-level effect is modest but consistent (5 of 6 antibiotics, 12 resampled splits each).
The protein-level effect is dramatic. **We report the lower numbers throughout.**

> An early single-split run showed one antibiotic moving the *wrong* way — pure noise. Every metric
> here is the mean of 12 resampled splits, with standard deviations shown in the interface.

## What we tried that failed

We hypothesised that representing genes by **protein language model embeddings** (ESM-2) rather
than by name would let the system generalise to resistance genes never seen in training — since a
novel carbapenemase should embed near known ones. We tested it properly and it **half worked**:

- ✅ Holding out all 30 carbapenemases, **100% were still recognised as beta-lactam machinery.** A
  gene-presence checklist cannot do this at all — an unseen gene has no feature to be zero.
- ❌ **0% were identified as carbapenem-hydrolyzing.** All were classified as ordinary
  beta-lactamases.

That distinction is the whole clinical question: TEM and SHV are ordinary beta-lactamases and
meropenem works fine against them. So embeddings captured the chemistry and missed the severity,
and we dropped the claim. They survive in the shipped system in the role they actually earned —
**detecting that unfamiliar machinery is present**, which triggers abstention.

Full detail, including the measurements that killed it, is in `VALIDATION_FINDINGS.md`.

## Architecture

```
BV-BRC API ──> pipeline/build.py ──> ui/predictions.js ──> ui/index.html
                     │
                     ├─ gene-presence features        600 genomes × 101 products
                     ├─ per-drug calibrated model     HistGradientBoosting + isotonic
                     ├─ lineage-aware evaluation      GroupShuffleSplit on MLST × 12
                     ├─ novelty gate                  rare/unseen resistance machinery
                     ├─ SHAP evidence                 per-prediction attribution
                     └─ clinical annotations          pipeline/annotations.py
```

The interface never calls a model — predictions are computed offline and embedded, so the demo
loads instantly and cannot fail live. The tech video shows the pipeline running for real.

## Run it

```bash
pip3 install pandas scikit-learn shap
python3 pipeline/build.py     # ~3 min: pulls metadata, trains, exports
open ui/index.html            # no server required
```

Optional, for the embedding experiments: `pip3 install torch transformers`

## Data

**BV-BRC** (Bacterial and Viral Bioinformatics Resource Center) — public, no login.

Critically, we filter to `evidence = "Laboratory Method"`. BV-BRC serves 17.2M AMR records but only
**1.28M are laboratory-measured**; the rest are another model's predictions. Training on those
teaches you to imitate a classifier rather than learn biology. The organisers flag this too.

Isolates are real human clinical samples — blood, urine, respiratory, wound.

## Honest limitations

- *Klebsiella pneumoniae* only.
- Predictions precomputed for demo speed; pipeline runs live in the tech video.
- The novelty gate detects that unfamiliar machinery is **present**; it does not identify the
  mechanism.
- Clean-vs-cluttered genetic background analysis rests on small samples (n=10, n=14) and is
  indicative, not conclusive.
- Gene presence is not gene expression — a resistance gene can be present and silent. We observed
  exactly this: an isolate carrying Tet(D) that was tetracycline-susceptible.
- Not a medical device. Every treatment decision stays with a qualified clinician; this system
  narrows the window in which that decision is a guess, and hands ambiguous cases back to the lab.

## Team

Built by a team of four: an AI engineer, a healthcare professional who defined the clinical
annotations and abstention thresholds, a business/finance lead, and a communications lead.
