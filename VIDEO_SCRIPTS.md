# Video scripts — Hack-Nation submission

Three videos, one minute each: **Tech**, **Demo**, **Team**. Uploaded at projects.hack-nation.ai.

Narration below is timed at ~150 words/minute. Word counts are given so you can check pace before
recording. Read slightly slower than feels natural — judges are watching many of these.

---

## 1. TECH VIDEO (60s)

Support's guidance for this one merges what the kickoff called "pitch" with technical depth. It
should answer: what does it do, how is it built, what did you solve, what does it score. Cover the
problem fast and spend most of the minute on evidence.

**Visual:** open on the worklist, cut to a specimen page around 0:20, cut to the validation page at
0:35, hold on the six-tier table for the closing numbers.

> When a patient has a bloodstream infection, the lab needs 48 to 72 hours to find out which
> antibiotics still work. Until then the clinician guesses. Genome Firewall reads the bacterium's
> genome and predicts susceptibility in about a second.
>
> The hard part isn't the prediction. Any classifier can produce a number. The hard part is knowing
> when not to answer — because telling a doctor a drug will work when it won't is how a patient
> dies.
>
> So we built four gates in front of the model. It abstains on low confidence, on resistance
> machinery it has never seen, on genomes that look incompletely assembled, and — the one that
> matters — when a prediction contradicts the isolate's own resistance profile.
>
> We proved that gate was necessary. On twelve engineered cases where we deleted the carbapenemase
> to mimic an unknown mechanism, the raw model returned a confident "susceptible" all twelve times.
> Twelve lethal errors. With the coherence gate: twelve out of twelve caught.
>
> Gradient boosting, isotonically calibrated, on eighteen hundred isolates. Validated six ways
> including a locked holdout and an external database. It beats the clinical rule baseline on
> fourteen of twenty-one antibiotics.

**156 words.** If you run long, cut the last sentence of paragraph one.

**On screen while you talk** (text overlays, no narration needed):
- `48–72h → ~1.2s`
- `4 abstention gates`
- `0/12 → 12/12`
- `+0.044 mean AUC vs clinical rule · 14 wins / 6 ties / 1 loss`

---

## 2. DEMO VIDEO (60s)

Show the product working. Do not explain architecture — that's the tech video's job. The single
most persuasive thing you can show is the system **refusing to answer**, because every other team's
demo will show a confident prediction.

**Record this exact sequence. Rehearse once, then record — it fits in 60s with room.**

| Time | Action | Say |
|---|---|---|
| 0:00 | Worklist page, cursor moving down the queue | "This is a hospital microbiology worklist. Sixteen isolates, each one a real patient specimen awaiting susceptibility results." |
| 0:08 | Click a specimen with resistant calls | "Opening one gives the full antibiotic panel — susceptible agents first, so the treatable options are what you read." |
| 0:16 | Click an antibiotic → dialog opens | "Every call opens to its evidence. This one is driven by a chromosomal mutation — and that matters, because gene-lookup tools screen for acquired genes only. They report this isolate susceptible. It isn't." |
| 0:28 | Navigate to New analysis | "Now a genome the system has never seen." |
| 0:32 | Click **Unfamiliar machinery**, let it run | "This isolate carries resistance machinery absent from training." |
| 0:38 | Results land, all deferred | "It refuses. All ten antibiotics deferred to culture — because the model can't score machinery it doesn't recognise, and a confident wrong answer is worse than no answer." |
| 0:48 | Click **Lightly armed isolate**, let it run | "And when the evidence is there, it commits — seven agents cleared for therapy, in about a second." |
| 0:56 | Hold on the result | "Real model, real inference, on an isolate held out of training." |

**Notes:**
- Inference is ~1.2s. **Do not cut it out** — the fact that it's genuinely running is the point.
  Let the stepper play.
- Say the word "refuses" clearly. That's the memorable moment.
- If you have to lose something, lose the 0:08 step.

---

## 3. TEAM VIDEO (60s) — already covered

Support: *"you just have 60 sec to introduce your team, no complicated things need to be mentioned,
just some voice over of who is submitting."*

**Filming alone is fine.** You are an online team; support explicitly described this as voice-over
of who is submitting. Name each of the four of you and one line on contribution. Nobody is required
to be on camera.

---

## Numbers you can defend

Every figure here is reproducible from the repo. Nothing is rounded in our favour.

**Scale**
- 1,863 *K. pneumoniae* isolates with paired AST phenotype + AMRFinderPlus genotype (NCBI Pathogen Detection)
- 1,590 train / 273 quarantined holdout, split before any modelling
- 7,273 genomes external validation (BV-BRC)
- 23 antibiotics modelled

**Six validation tiers** (mean AUC across 23 antibiotics)

| tier | AUC | what it tests |
|---|---|---|
| random split | 0.914 | optimistic — reported only to show the gap |
| clone-aware split | 0.900 | removes near-identical isolates straddling the split |
| locked holdout | 0.916 | quarantined before modelling |
| external (BV-BRC) | 0.826 | different database, **no mutation features available** |
| temporal | 0.798 | train on past, test on future |
| geographic | 0.903 | train on some countries, test on others |

**Against the clinical rule baseline** — ResFinder/PointFinder-style gene lookup, the thing labs
actually use:
- model **0.869** vs rule **0.825** → **+0.044**
- **14 wins / 6 ties / 1 loss**

**Cross-species** — the honest result, and worth saying out loud:
- Transferring a Klebsiella model to another species **fails** (0.768 vs rule 0.874). We don't ship it.
- **Retraining** the same pipeline per organism works, including across the Gram divide:
  *S. aureus* (Gram-positive, 1,082 isolates) → **mean AUC 0.946**, 2 wins / 1 tie / 1 loss.
  Oxacillin 0.984 ties the rule — correct, because there *mecA* genuinely is the mechanism.

**Adversarial edge-case benchmark** — 93 cases we built by perturbing real isolates (deleting the
carbapenemase, stripping the assembly, mutation-only genomes, conflicting evidence):
- 85 scored, **73 passed (85%)**
- **novel mechanism: 12/12, zero lethal errors** — this is the clean headline, use this one
- **3 lethal errors** across scored cases; **7 across all 93 run**

Report the 7, not the 3. The four-case difference sits entirely in `invisible_mechanism`, where the
discriminating information is absent from the feature space by construction — we exclude those from
the pass rate but *not* from the error count. Volunteering this is stronger than being caught on it.

**Latency:** ~1.2s live inference vs 48–72h culture AST.

---

## Things NOT to say

Judges probe. These are the claims that would fall apart:

- ❌ "Works on any bacterial species." It does not. Say "retrains per organism; proven on Klebsiella and *S. aureus*."
- ❌ "Replaces culture." It does not. It's a bridge for the 48–72h window; culture remains ground truth.
- ❌ Any single accuracy headline without naming the split. The random-split number is inflated and we know it.
- ❌ Protein language model embeddings improving prediction. We tested it; it did not. They're used for novelty detection only.
- ❌ "3 lethal errors" as the headline. That figure counts scored cases only. The true total across all 93 cases is 7. Quote 7, then explain where the other 4 live.

The strongest move in Q&A is volunteering a limitation before they find it. We have real ones and
they are documented in `VALIDATION_FINDINGS.md`.
