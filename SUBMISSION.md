# Submission package

Everything due **9:00 AM ET / 4:00 PM Cairo**. Upload to projects.hack-nation.ai.

---

## 1. Project summary (289 words — paste as-is or tighten)

**Genome Firewall**

A patient with a serious bacterial infection waits 48–72 hours for culture-based susceptibility
testing. Until it returns, the doctor is guessing which antibiotic will work. Guess too narrow and
the infection advances unchecked; in bloodstream infection, delayed effective therapy drives
mortality. Guess too broad and last-resort drugs are burned, accelerating the resistance that
created the problem.

Sequencing takes hours. Genome Firewall predicts, for each antibiotic, whether it will work — with
a calibrated probability and the resistance genes that drove the call, annotated for clinicians.

The difference is what it does when it doesn't know. A standard classifier is forced to answer.
Shown a genome carrying a resistance mechanism it was never taught, the gene checklist reads clean
— indistinguishable from genuine susceptibility — and it returns "susceptible" with high
confidence. That confidently wrong answer removes the caution that would otherwise have protected
the patient. Our system asks first whether it recognises the machinery present, and defers to the
laboratory when it does not.

We also measured something uncomfortable. Reported performance in this field is systematically
inflated by relatedness, at two independent levels. Splitting genomes by bacterial lineage rather
than at random drops mean AUC from 0.915 to 0.892 across six antibiotics (12 resampled splits each).
Splitting proteins by sequence family drops embedding accuracy from 0.955 to 0.451. We report the
lower numbers throughout, and the interface lets you toggle between them.

We tested whether protein language-model embeddings could recognise a resistance family held out of
training. They identified 100% as beta-lactam machinery but 0% as carbapenem-hydrolyzing — the
distinction that decides whether the last-resort drug works. We dropped the claim and kept
embeddings only for novelty detection.

Built on BV-BRC laboratory-confirmed phenotypes, filtered to exclude model-generated labels.

---

## 2. Demo video — shot list

**Rule: working product on screen within 10 seconds. No title cards. No team intros.**
Target 2–3 minutes.

| Time | Screen | Narration (clinician voice) |
|---|---|---|
| 0:00 | UI already open, lead isolate loaded | "This is a Klebsiella isolate from a patient. Right now, the lab needs two to three days to tell the doctor which antibiotics will work." |
| 0:12 | Point at the 48–72h banner | "For those days, treatment is a guess." |
| 0:20 | Antibiotic table | "From the genome we get an answer now. Meropenem will fail. Ciprofloxacin will fail. But amikacin should work — and that's the drug this patient needs." |
| 0:40 | Click meropenem → evidence drawer | "And it shows why. A KPC carbapenemase — the enzyme that destroys last-resort carbapenems." |
| 0:55 | Scroll drawer to a passenger gene | "It also marks genes that are only along for the ride. This one sits on the same plasmid but doesn't cause carbapenem resistance. We say so, rather than implying causation we haven't earned." |
| 1:10 | Scroll to an unexplained feature | "And where the model is leaning on something with no known mechanism, we flag it as a lineage marker — not biology." |
| 1:25 | Select an isolate with an INDETERMINATE row | "Here it refuses to answer. There's resistance machinery in this genome it doesn't recognise." |
| 1:40 | Hold on the indeterminate row | "A classifier would have guessed. If it guessed 'susceptible' and it was wrong, the patient gets a drug that does nothing while a bloodstream infection advances. A confidently wrong model is more dangerous than no model." |
| 1:55 | Click **Methods & Evaluation** | "Last thing — and it's the part we're most proud of." |
| 2:05 | **Flip the split toggle** | "This is what most approaches report. And this is what happens when you stop letting closely-related bacteria appear in both training and test. We report the lower number." |
| 2:20 | Scroll to the protein-level panel | "Same illusion one level down — 0.955 becomes 0.451. We found it by checking our own work." |

**The toggle flip is the money shot. Land it cleanly and let it breathe.**

---

## 3. Tech video — structure

Target 3 minutes. This is where technical depth is actually scored, so go **deep on one thing**
rather than shallow on five.

1. **(0:00–0:20) Architecture, briefly.** One diagram. BV-BRC → features → calibrated model →
   novelty gate → evidence. Say the interface reads precomputed JSON so the demo can't fail live,
   and that this script is the real thing.
2. **(0:20–0:50) Run `pipeline/build.py` on camera.** Show the terminal. Real output, real numbers.
3. **(0:50–2:10) The leakage finding — the deep dive.**
   - Show the data filter: 17.2M AMR records, only 1.28M laboratory-measured. Explain that the rest
     are another model's predictions and training on them teaches imitation, not biology.
   - Show `GroupShuffleSplit` on MLST. Explain descent and why random splits leak.
   - **Show that an early single-split run moved one drug the wrong way**, which is why every number
     is the mean of 12 resampled splits. Admitting this reads as rigour.
   - Show the protein-level result: 0.955 → 0.451.
4. **(2:10–2:40) The experiment that failed.** Held out all 30 carbapenemases. 100% recognised as
   beta-lactam machinery, 0% as carbapenem-hydrolyzing. Explain why that kills the strong claim —
   TEM and SHV are beta-lactamases and meropenem works fine against them — and what we kept instead.
5. **(2:40–3:00) Limitations, stated plainly.** Klebsiella only. Small samples on the
   clean/cluttered analysis. Gene presence is not gene expression.

**Do not overclaim. Every number in this video is reproducible from the repo.**

---

## 4. Team video

Three sentences of founder-market fit per person, ending in why *this* team ships *this* product.
Not resumes. Lead with fit; let the composition be the evidence, not the point.

- **Clinician** — has watched the 48-hour guess happen. Defined the gene annotations and set the
  abstention thresholds, because the two errors are not equally bad.
- **AI engineer** — built the pipeline, and found the leakage by checking work that already looked
  good.
- **Business/finance** — who buys this: hospital labs, antibiotic stewardship programmes, ICUs, and
  what a day of inappropriate therapy costs.
- **Comms** — made the uncertainty legible, which is the entire product.

---

## 5. Checklist

- [ ] Project summary (above)
- [ ] Demo video
- [ ] Tech video
- [ ] Team video
- [ ] Public GitHub repo — include `README.md`, `VALIDATION_FINDINGS.md`, `BLUEPRINT.md`
- [ ] Zipped code
- [ ] Dataset link — **BV-BRC**, https://www.bv-brc.org/ (state the `Laboratory Method` filter)
- [ ] All team members added on projects.hack-nation.ai
- [ ] Challenge declared in Discord

---

## 6. Anticipated judge questions

**"Isn't this just a database lookup of known resistance genes?"**
No — gene presence and clinical outcome come apart in specific, learnable ways. We have an isolate
carrying Tet(D), a tetracycline resistance gene, that is tetracycline-susceptible. Presence is not
expression. That's why we model probability and abstain rather than looking up a table.

**"Your accuracy is lower than paper X."**
Probably, because paper X almost certainly used a random split. We measured that exact inflation and
report the honest number. Ask them what their lineage-aware number is.

**"Why not use a protein language model?"**
We did, and we tested it. It recognises the chemistry but not the severity — 100% of held-out
carbapenemases were called beta-lactamases, 0% carbapenem-hydrolyzing. We kept it for novelty
detection, which is what it actually earned.

**"How would this be deployed?"**
It slots in after sequencing and before culture results. It does not replace the laboratory; it
shrinks the window in which treatment is a guess, and it hands ambiguous cases straight back to the
lab.
