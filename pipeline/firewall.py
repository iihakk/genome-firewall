"""The decision layer: probability in, defensible call out.

Three gates, added in the order the evidence forced.

1. CONFIDENCE   abstain inside an asymmetric band. Calling a drug susceptible when it is
                resistant can kill; the reverse wastes a last-resort drug. The band is not
                centred on 0.5 for that reason.

2. NOVELTY      abstain when the genome carries resistance machinery absent from training.
                Catches unfamiliar mechanisms that are PRESENT.

3. COHERENCE    abstain when the prediction contradicts the isolate's own resistance profile.

Gate 3 exists because the edge-case benchmark proved gates 1 and 2 were insufficient. On 12 cases
where a carbapenemase was deleted to mimic an unseen mechanism, the model returned a confident
SUSCEPTIBLE every time — 12 lethal errors. Novelty detection could not help: deleting a gene does
not make a genome look unfamiliar, it makes it look ordinary. The signal is not in what is
present, it is in the mismatch between one prediction and the rest of the picture.

Coherence works by asking what the isolate's nearest neighbours in the training set actually did.
A genome whose overall resistance profile matches isolates that were 90% meropenem-resistant, but
which we are about to call susceptible, is telling us something is missing from the evidence.
"""

import numpy as np

# Asymmetric by clinical judgement — the clinician sets these, not a grid search.
ABSTAIN_LO, ABSTAIN_HI = 0.35, 0.65
NOVEL_LO, NOVEL_HI = 0.25, 0.75      # widened band once unfamiliar machinery is present
COHERENCE_K = 25                      # neighbours consulted
COHERENCE_GAP = 0.45                  # |neighbour rate − our probability| that triggers a refusal
COHERENCE_MIN_SIM = 0.30              # ignore neighbours that aren't really similar
SPARSE_PCT = 5                        # below this percentile of determinant count, suspect a
                                      # truncated assembly rather than a clean genome


def jaccard(a, B):
    """Similarity of one binary feature row against a matrix of them."""
    inter = B @ a
    union = B.sum(1) + a.sum() - inter
    return np.divide(inter, np.maximum(union, 1), dtype=float)


class Firewall:
    def __init__(self, model, vocab, Xtrain, ytrain, known_tokens):
        self.model = model
        self.vocab = list(vocab)
        self.idx = {t: i for i, t in enumerate(self.vocab)}
        self.X = Xtrain.astype(np.int8)
        self.y = np.asarray(ytrain)
        self.known = set(known_tokens)
        # Completeness reference: how many determinants a normal isolate of this species carries.
        counts = self.X.sum(1)
        self.median_called = int(np.median(counts))
        self.sparse_cut = int(np.percentile(counts, SPARSE_PCT))

    def vectorise(self, tokens):
        x = np.zeros(len(self.vocab), dtype=np.int8)
        for t in tokens:
            j = self.idx.get(t)
            if j is not None:
                x[j] = 1
        return x

    def coherence(self, x, prob):
        """What did the most similar training isolates actually do?"""
        sims = jaccard(x, self.X)
        order = np.argsort(-sims)[:COHERENCE_K]
        keep = order[sims[order] >= COHERENCE_MIN_SIM]
        if len(keep) < 5:
            return None, None, None
        rate = float(self.y[keep].mean())
        return rate, float(sims[keep].mean()), abs(rate - prob)

    def assess(self, tokens):
        toks = set(tokens)
        unknown = sorted(toks - self.known)
        x = self.vectorise(toks)
        prob = float(self.model.predict_proba(x.reshape(1, -1))[0, 1])

        rate, sim, gap = self.coherence(x, prob)
        n_called = int(x.sum()) + len(unknown)

        call, reason = None, None
        if ABSTAIN_LO <= prob <= ABSTAIN_HI:
            call, reason = "INDETERMINATE", "confidence below clinical threshold"

        # Unrecognised machinery blocks a SUSCEPTIBLE call at ANY confidence. The probability was
        # computed without that evidence, so a low number reflects what the model could see, not
        # what is there. It does not block a RESISTANT call — that is already the cautious side.
        elif unknown and prob <= 0.5:
            call = "INDETERMINATE"
            reason = (f"{len(unknown)} unrecognised resistance protein(s) present — a susceptible "
                      f"call cannot be justified without knowing what they do")

        # An unusually sparse genome is more likely an incomplete assembly than a genuinely clean
        # isolate, and absence of evidence read off a partial genome is not evidence of absence.
        elif self.sparse_cut and n_called < self.sparse_cut and prob <= 0.5:
            call = "INDETERMINATE"
            reason = (f"only {n_called} resistance determinants detected where comparable isolates "
                      f"carry {self.median_called} — assembly may be incomplete")

        elif gap is not None and gap >= COHERENCE_GAP:
            call = "INDETERMINATE"
            reason = (f"prediction contradicts this isolate's resistance profile — "
                      f"{rate:.0%} of its {COHERENCE_K} closest matches were resistant")
        else:
            call = "RESISTANT" if prob > 0.5 else "SUSCEPTIBLE"

        return dict(call=call, probability=round(prob, 3), reason=reason,
                    unknown_machinery=unknown, n_determinants=n_called,
                    neighbour_resistance_rate=None if rate is None else round(rate, 3),
                    neighbour_similarity=None if sim is None else round(sim, 3),
                    coherence_gap=None if gap is None else round(gap, 3))
