"""Live analysis as a Vercel Python serverless function.

This replaces the Node route that shelled out to python3 — Vercel's Node runtime has no
Python, so the model runs here instead, natively. It is a self-contained port of
pipeline/serve_model.py's predict path plus the canon() normaliser and the Firewall: no import
of the training modules, and deliberately no pandas, to keep the function bundle under Vercel's
size limit.

The model and vocabulary are loaded once at module import, so a warm container reuses them and
only the first (cold) request pays the load cost.
"""

import json
import os
import pickle
import re
import time
from http.server import BaseHTTPRequestHandler

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_CONF = 0.5

# ── normalisation (ported from pipeline/features.py) ─────────────────────────
_VOCAB = None


def vocab_map():
    global _VOCAB
    if _VOCAB is None:
        p = os.path.join(HERE, "vocab_map.json")
        _VOCAB = json.load(open(p)) if os.path.exists(p) else {}
    return _VOCAB


def _gene_from_mutation(token):
    body = token.split(":", 1)[1] if ":" in token else token
    return re.split(r"[_ ]", body)[0].lower() or None


def canon(token):
    if not token:
        return None
    r = vocab_map().get(token)
    if not r or r.get("confidence", 0) < MIN_CONF:
        return None
    fam = r.get("family")
    kind = str(r.get("kind") or "")
    if not fam and token.startswith(("POINT:", "TRUNC:")):
        fam = _gene_from_mutation(token)
    if not fam:
        return None
    fam = re.sub(r"[^A-Za-z0-9()'\-]", "", str(fam)).lower()
    if not fam or fam in ("null", "none", "unknown"):
        return None
    k = kind.lower()
    if k in ("point_mutation", "point") or token.startswith("POINT:"):
        return f"POINT:{fam}"
    if k in ("truncation", "trunc") or token.startswith("TRUNC:"):
        return f"TRUNC:{fam}"
    return fam


def canon_raw(raw):
    t = (raw or "").strip()
    if not t or t.upper() in ("NULL", "-"):
        return None
    if t.endswith(("=MISTRANSLATION", "=PARTIAL")):
        return None
    body = t.split("=")[0]
    candidates = []
    if t.endswith("=POINT"):
        candidates += [f"POINT:{body}", f"TRUNC:{body}"]
    elif re.search(r"fsTer|Ter\d*$", body):
        candidates += [f"TRUNC:{body}", f"POINT:{body}", f"TRUNC:{re.split(r'_', body)[0]}"]
    else:
        candidates += [t, body, re.sub(r"-\d+$", "", body)]
    for c in candidates:
        got = canon(c)
        if got:
            return got
    if t.endswith("=POINT") or re.search(r"fsTer|Ter\d*$", body):
        gene = re.split(r"[_ ]", body)[0].lower()
        if gene:
            return ("TRUNC:" if re.search(r"fsTer|Ter\d*$", body) else "POINT:") + gene
    return None


# ── firewall (ported from pipeline/firewall.py) ──────────────────────────────
ABSTAIN_LO, ABSTAIN_HI = 0.35, 0.65
COHERENCE_K = 25
COHERENCE_GAP = 0.45
COHERENCE_MIN_SIM = 0.30
SPARSE_PCT = 5


def jaccard(a, B):
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
        elif unknown and prob <= 0.5:
            call = "INDETERMINATE"
            reason = (f"{len(unknown)} unrecognised resistance protein(s) present — a susceptible "
                      f"call cannot be justified without knowing what they do")
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
                    neighbour_resistance_rate=None if rate is None else round(rate, 3))


# ── model, loaded once per container ─────────────────────────────────────────
_BUNDLE = None


def bundle():
    global _BUNDLE
    if _BUNDLE is None:
        with open(os.path.join(HERE, "models.pkl"), "rb") as f:
            _BUNDLE = pickle.load(f)
    return _BUNDLE


def predict(profile):
    b = bundle()
    known = set(b["known"])
    raw = profile.get("determinants", [])
    canonical, unmapped = set(), []
    for r in raw:
        c = canon_raw(r)
        if c:
            canonical.add(c)
        else:
            unmapped.append(r)

    results, novel = [], set()
    for drug, d in b["drugs"].items():
        fw = Firewall(d["model"], d["vocab"], d["X"], d["y"], known)
        a = fw.assess(canonical)
        novel.update(a["unknown_machinery"])
        results.append({
            "drug": drug,
            "call": a["call"],
            "probability": a["probability"],
            "reason": a["reason"],
            "unknownMachinery": a["unknown_machinery"],
            "neighbourResistanceRate": a["neighbour_resistance_rate"],
        })

    order = {"SUSCEPTIBLE": 0, "INDETERMINATE": 1, "RESISTANT": 2}
    results.sort(key=lambda r: (order[r["call"]],
                                r["probability"] if r["call"] == "SUSCEPTIBLE"
                                else -r["probability"]))
    return {
        "accession": profile.get("accession", "unknown"),
        "organism": profile.get("organism", "Klebsiella pneumoniae"),
        "source": profile.get("source"),
        "determinantsSubmitted": len(raw),
        "determinantsRecognised": sorted(canonical),
        "determinantsUnrecognised": unmapped,
        "determinantsNovel": sorted(novel),
        "results": results,
    }


# ── Vercel handler ───────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            profile = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send(400, {"error": "Could not parse the request body as JSON."})
        if not isinstance(profile, dict) or not isinstance(profile.get("determinants"), list):
            return self._send(400, {"error": "Expected a JSON profile with a `determinants` array."})
        try:
            started = time.time()
            result = predict(profile)
            result["elapsedMs"] = int((time.time() - started) * 1000)
            return self._send(200, result)
        except Exception as e:  # noqa: BLE001 — surface the message to the caller, not a 500 page
            return self._send(500, {"error": f"analysis failed: {e}"})

    def do_GET(self):
        self._send(200, {"ok": True, "endpoint": "POST a determinant profile to analyse"})
