# Genome Firewall — build blueprint

**Thesis:** everyone else ships a classifier that always answers. We ship a firewall that knows
what it doesn't know — and we prove, with measurements at two independent levels, that the
confident numbers everyone else reports are inflated.

---

## 1. Architecture

Deliberately decoupled: the ML runs offline and **exports JSON**; the UI is a static app that reads
it. This means the demo cannot crash, loads instantly for video recording, and the builder spends
remaining hours on modelling and design instead of fighting a server at 4 AM.

```
  BV-BRC API ──> pipeline (python, offline) ──> predictions.json ──> UI (static, no backend)
                        │
                        ├─ gene-presence features      (verified: mean AUC 0.922)
                        ├─ ESM-2 protein embeddings    (verified: 37 ms/protein)
                        ├─ per-drug calibrated model   (isotonic)
                        ├─ lineage-aware evaluation    (verified: +0.044 AUC inflation)
                        ├─ novelty gate                (verified: 100% coarse-family recall)
                        ├─ SHAP evidence               (verified: KPC dominates meropenem)
                        └─ therapy ranking             (clinician-defined)
```

**Honesty rule:** the UI states plainly that predictions are precomputed for demo speed, and the
tech video shows the pipeline running live. Never imply live inference we don't do.

### The decision logic (this is the product)

For each antibiotic:

```
1. calibrated p(resistant)              — isotonic-calibrated gradient boosting
2. novelty score                        — is there resistance machinery we don't recognise?
3. IF novelty高 OR p in [lo, hi] band   -> INDETERMINATE, defer to culture
   ELSE                                 -> RESISTANT / SUSCEPTIBLE with confidence
4. evidence                             — SHAP drivers + clinician annotation + CARD link
5. therapy rank                         — expected utility, not just probability
```

The abstention band `[lo, hi]` is **set by the clinician**, asymmetrically: calling a drug
susceptible when it is resistant can kill; calling it resistant when susceptible wastes a
last-resort drug. Those errors are not equal and the thresholds must not be either.

---

## 2. UI / UX specification

**Design language: clinical instrument, not dashboard.** Calm, dark, high contrast. Colour carries
*only* semantic meaning — never decoration. If it isn't telling the clinician something, it's grey.

### Palette

| Token | Value | Use |
|---|---|---|
| `bg` | `#0A0D13` | page |
| `surface` | `#12161F` | cards |
| `surface-2` | `#1A202C` | raised / hover |
| `border` | `#242B38` | hairlines |
| `text` | `#E8ECF4` | primary |
| `muted` | `#8792A6` | secondary |
| `resistant` | `#E5484D` | drug will fail |
| `susceptible` | `#30A46C` | drug should work |
| `indeterminate` | `#F5A524` | we refuse to call |
| `accent` | `#2DD4BF` | brand / focus |

Light mode mirrors this with the same semantics (judges may view on any device).

### Typography
- UI: `Inter`, system-ui fallback. Weights 400/500/600 only.
- Data — gene names, isolate IDs, probabilities: `ui-monospace / JetBrains Mono`. Monospace for
  anything a scientist would want to compare column-wise.
- Scale: 12 / 13 / 14 / 16 / 20 / 28 / 40. Nothing else.

### Layout — three zones

```
┌────────────────────────────────────────────────────────────────────────────┐
│  ⬡ GENOME FIREWALL          Isolates   Methods & Evaluation        [◐]     │  56px header
├──────────────┬─────────────────────────────────────────────────────────────┤
│  ISOLATES    │  Klebsiella pneumoniae · 573.14422                          │
│              │  blood culture · ST258 · Homo sapiens                       │
│ ▸ 573.14422  │                                                             │
│   blood      │  ┌───────────────────────────────────────────────────────┐  │
│ ▸ 573.13892  │  │ ◷  Culture AST reports in 48–72 h. This: available now │  │
│   urine      │  └───────────────────────────────────────────────────────┘  │
│ ▸ 573.14201  │                                                             │
│   sputum     │   ANTIBIOTIC          CALL          CONFIDENCE              │
│              │   meropenem           RESISTANT     ▓▓▓▓▓▓▓▓░░ 0.91         │
│              │   ciprofloxacin       RESISTANT     ▓▓▓▓▓▓▓░░░ 0.84         │
│              │   gentamicin          SUSCEPTIBLE   ▓▓▓▓▓▓▓▓▓░ 0.93         │
│              │   amikacin            ⚠ INDETERMINATE  ▓▓▓▓░░░░░░ 0.58      │
│              │      └ unfamiliar resistance machinery · deferred to culture│
└──────────────┴─────────────────────────────────────────────────────────────┘
```

Clicking a row slides in an **evidence drawer** from the right (320–420px, `transform` +
`opacity`, 180ms `cubic-bezier(.4,0,.2,1)`):

```
   EVIDENCE — meropenem
   ────────────────────────────────────
   p(resistant) 0.91   ·   calibrated
   
   KPC-family carbapenemase        +0.42  ████████████
     Hydrolyses carbapenems including meropenem.
     Hospital-outbreak associated.        [CARD ↗]
   
   AAC(6')-Ib                      +0.07  ██
     Aminoglycoside-modifying; co-carried
     on the same plasmid. Not a carbapenem
     mechanism — linkage, not causation.
   ────────────────────────────────────
   ⚠ 1 protein in this genome resembles
     beta-lactam machinery we do not
     recognise. Treat with caution.
```

That last block is the firewall speaking. It's the most important box in the product.

### The Methods page — where we win

This must be **prominent navigation, not a footnote.** It carries the differentiator.

- A single **toggle: `Random split` ⟷ `Lineage-aware split`**. Flipping it animates every AUC
  number downward. This is the demo's money shot — a physical gesture that makes the field's
  inflation visible. Number transitions ~400ms, eased, with the delta appearing in amber.
- Beneath it, the second level: **protein family-aware split**, `0.955 → 0.451`.
- A reliability diagram (calibration) and Brier scores.
- One plain-language paragraph: what leakage is, why it inflates, why we report the lower number.

### Interaction rules
- Focus rings on all interactive elements (`accent`, 2px). Keyboard navigable.
- `prefers-reduced-motion` disables the number animation — show final values.
- Tables scroll inside their own container; the page body never scrolls horizontally.
- Every probability displays 2 decimals, monospace, right-aligned so digits line up.
- No spinners in the demo — data is embedded, everything is instant.

### What makes it feel expensive
Restraint. One accent colour. Hairline borders instead of shadows. Consistent 8px spacing grid.
Numbers in monospace, aligned. No gradients, no glassmorphism, no emoji in the product chrome.
Generous line-height (1.5) in prose, tight (1.2) in data. The whole thing should look like it
belongs in a hospital lab, not a hackathon.

---

## 3. Build order — with cut lines

| # | Task | Est | Priority |
|---|---|---|---|
| 1 | Scale data pull; cache to disk (more genomes, 6–8 drugs) | 1.0 | **must** |
| 2 | Final per-drug calibrated models + lineage-aware metrics → `metrics.json` | 1.5 | **must** |
| 3 | Novelty gate from ESM embeddings | 1.0 | **must** |
| 4 | Abstention logic w/ clinician thresholds | 0.5 | **must** |
| 5 | SHAP evidence + join clinician gene annotations | 1.0 | **must** |
| 6 | Export `predictions.json` for ~20 demo isolates | 0.5 | **must** |
| 7 | UI build | 3.0 | **must** |
| 8 | Therapy ranking layer | 1.0 | *high* |
| 9 | Videos + README + submission | 3.0 | **must** |
| 10 | E. coli cross-species check | 1.0 | *stretch* |

**Cut in this order if time runs short:** 10 → 8 → therapy ranking becomes a static panel → reduce
demo isolates to 6. **Never cut 2, 3, or 9.** The evaluation *is* the submission; the videos are a
third of the score.

---

## 4. Deliverable mapping

| Required | Source |
|---|---|
| 150–300 word summary | business/finance, written last |
| Demo video | UI walkthrough: isolate → evidence → indeterminate → Methods toggle |
| Tech video | pipeline running live + the two-level leakage finding |
| Team video | founder-market fit, clinician leads |
| GitHub repo | pipeline + UI + `VALIDATION_FINDINGS.md` |
| Dataset | BV-BRC, cite the lab-confirmed filter explicitly |

---

## 5. Honesty ledger — state these on camera

Small samples on the clean/cluttered background split (n=10, n=14). Predictions precomputed for
demo speed. Klebsiella only unless the E. coli check lands. Novelty gate detects *unfamiliar
machinery*, it does not identify the mechanism. The embedding approach **failed** at fine-grained
severity — we tested it, it didn't work, and we say so.

Admitted limits read as rigour to judges from OpenAI, Databricks and MIT. Overclaiming dies in Q&A.
