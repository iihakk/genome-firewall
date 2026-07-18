# Validation findings — protein-embedding approach

**Verdict: the strong version does not hold. Do NOT restructure the build around it.
A weaker version is genuinely useful, already working, and cheap to add.**

All numbers below are measured on this machine, not estimated.

---

## Feasibility gates — both PASS

| Gate | Result |
|---|---|
| Run a protein language model here | ✅ ESM-2 (35M) loads in 52s, **37 ms/protein** on CPU. 2,000 proteins ≈ 1.2 min. No GPU needed. |
| Get protein sequences + function labels | ✅ `genome_feature` → `aa_sequence_md5` → `feature_sequence`. Gathered **2,870 proteins**, 1,580 labelled into 8 resistance classes. |

So it was never a *feasibility* dead end. It's a *scientific* one.

---

## The science — what actually happened

### Embeddings do encode resistance function, but far less than they first appear

| Evaluation | Accuracy |
|---|---|
| Random 5-fold CV | **0.955** |
| **Family-aware GroupKFold** | **0.451** |
| Chance | 0.224 |

**Naive cross-validation overstated performance by +0.504.** Resistance proteins come in
families of near-identical variants (KPC-2, KPC-3, KPC-18, KPC-98…). A random split puts
variants of the same protein in both train and test, so the model scores by recognising a
sequence it has effectively already seen.

This is **the same leakage as the genome-lineage problem, one level down.** We now have it
measured at both levels — see "What to build" below.

Real signal exists (0.451 vs 0.224 chance), but it is modest, not the 95% first impression.

### Cosine similarity is weaker than it looks

Random protein pairs already sit at **mean cosine 0.810**. Same-class pairs 0.870, different-class
0.801 — a separation of only **0.069**. So a "0.98 similarity" nearest neighbour means little.
One held-out OXA-48 carbapenemase matched a *macrolide phosphotransferase* at 0.98.
**Do not build a nearest-neighbour demo on raw cosine.**

### The claim that failed — and it's the one that mattered

Holding out **all 30 carbapenemases** from training:

- ✅ **100% were correctly recognised as beta-lactam machinery** — the model knew they attack
  beta-lactam drugs without ever seeing a carbapenemase. A gene-presence checklist cannot do
  this at all; an unseen gene is not a zero, it has no feature.
- ❌ **0% were identified as carbapenem-hydrolyzing.** Every single one was classified as an
  *ordinary* beta-lactamase.

**Why that kills the headline pitch:** knowing "this is a beta-lactamase" does not tell you
meropenem fails. TEM and SHV are beta-lactamases and meropenem works fine against them. The
distinction between an ordinary beta-lactamase and a carbapenemase *is precisely the distinction*
that decides whether the last-resort drug works. Embeddings captured the chemistry and missed the
severity — so the demo "the checklist got it lethally wrong, we got it right" is **not supported**.

---

## The "before" half — also weaker than hypothesised, but informative

Hiding carbapenemase features from the gene-presence model, then testing on
carbapenemase-driven meropenem-resistant genomes:

| Model | mean p(resistant) | called SUSCEPTIBLE |
|---|---|---|
| Full (sees carbapenemase) | 0.906 | 2 / 24 |
| Crippled (mechanism hidden) | 0.688 | 5 / 24 |

Degrades, but does not collapse. **Why: carbapenemase genes travel on plasmids with a crowd of
other resistance genes**, so the model infers resistance from co-carried markers instead.

Splitting by how cluttered the genetic background is makes the real failure mode visible:

| Background | n | mean p(resistant) | called SUSCEPTIBLE |
|---|---|---|---|
| Cluttered (≥12 co-carried genes) | 14 | 0.811 | 1 / 14 |
| **Clean (<12 co-carried genes)** | **10** | **0.516** | **4 / 10** |

So the checklist model fails **specifically when a resistance mechanism arrives in a clean genetic
background** — which is exactly the novel-mechanism / fresh-horizontal-transfer scenario. It
survives otherwise only by leaning on linkage, which is a fragile crutch.

⚠️ Small samples (n=10, n=14). State this honestly if used.

---

## What to build instead

Drop the embedding *headline*. Keep three things:

**1. The two-level leakage finding — this is the real differentiator.**
We measured performance inflation at both levels of this problem:
- genome level, lineage-aware split: **+0.044 mean AUC** (meropenem +0.108)
- protein level, family-aware split: **+0.504 accuracy**

A coherent, measured argument that this whole field systematically overstates its numbers, plus a
system built to be honest about it. Almost no team will do this. It needs no new modelling — it's
already measured.

**2. Embeddings demoted to a novelty detector (honest, and already working).**
Don't ask embeddings to predict phenotype. Ask them only: *is there resistance-associated machinery
here that I don't recognise?* That is a far lower bar and it **is** supported — 100% coarse-family
recognition. Feeds straight into abstention: "unfamiliar beta-lactam machinery detected, defer to
culture." That is the firewall thesis, honestly earned. The embedding pipeline already runs.

**3. The verified core:** gene-presence model + lineage-aware evaluation + calibration + SHAP
evidence cards, plus the clinician's therapy-ranking layer.

---

## Cost of this investigation

About 40 minutes, and it saved us from building a headline demo that would have collapsed under a
judge's question. The embedding pipeline is built and reusable for use (2) above.
