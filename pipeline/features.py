"""Single source of truth for feature construction.

Every script previously built features slightly differently, and that inconsistency caused two
real errors: a regex word-boundary bug that silently dropped blaSHV/blaTEM/blaOXA, and junk
`POINT:null` / `TRUNC:null` columns formed when the classifier returned a kind but no family.
Both are fixed here, once.

Canonical token forms
---------------------
    blakpc              acquired resistance gene, collapsed to family (blaKPC-2 -> blakpc)
    POINT:gyra          target mutation, gene-level (measured: codon-level adds nothing)
    TRUNC:ompk35        gene truncation / porin loss

Sources
-------
    NCBI Pathogen Detection   AMRFinderPlus genotypes: genes + mutations + truncations.
                              Primary training source — richest features, self-consistent.
    BV-BRC                    gene presence only. Used as the EXTERNAL set, which doubles as a
                              degraded-input test since mutations are unavailable there.
"""

import csv
import json
import os
import re
from collections import defaultdict

import numpy as np
import pandas as pd

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
MIN_CONF = 0.5          # below this the classifier's family assignment is not trusted
PRUNE_LO, PRUNE_HI = 0.02, 0.98   # drop near-constant columns; they carry no signal

_VOCAB = None


def vocab_map():
    global _VOCAB
    if _VOCAB is None:
        p = os.path.join(DATA, "vocab_map.json")
        _VOCAB = json.load(open(p)) if os.path.exists(p) else {}
    return _VOCAB


def canon(token):
    """Annotation string -> canonical token, or None if not a usable determinant."""
    if not token:
        return None
    r = vocab_map().get(token)
    if not r or r.get("confidence", 0) < MIN_CONF:
        return None
    fam = r.get("family")
    if not fam:
        return None
    fam = re.sub(r"[^A-Za-z0-9()'\-]", "", str(fam)).lower()
    # A kind without a family produced 437 junk 'POINT:null' rows before this guard.
    if not fam or fam in ("null", "none", "unknown"):
        return None
    kind = r.get("kind") or ""
    if kind == "point_mutation":
        return f"POINT:{fam}"
    if kind == "truncation":
        return f"TRUNC:{fam}"
    return fam


def norm_drug(d):
    d = (d or "").strip().lower().replace("/", "-").replace(" ", "-")
    d = re.sub(r"-+", "-", d)
    return {
        "trimethoprim-sulphamethoxazole": "trimethoprim-sulfamethoxazole",
        "sulfamethoxazole-trimethoprim": "trimethoprim-sulfamethoxazole",
        "co-trimoxazole": "trimethoprim-sulfamethoxazole",
        "amoxicillin-clavulanic-acid": "amoxicillin-clavulanate",
        "ticarcillin-clavulanic-acid": "ticarcillin-clavulanate",
        "cephalothin": "cefalotin", "cefalothin": "cefalotin",
    }.get(d, d)


def load_ncbi(species="klebsiella"):
    """Primary source. Returns (feats, labels, meta) keyed by assembly accession.

    `meta['clone']` groups isolates sharing an identical raw genotype profile. NCBI publishes no
    MLST here, and exact-profile identity is a conservative clonal proxy: it will not catch all
    relatedness, but it stops literal duplicates straddling a train/test split.
    """
    path = os.path.join(DATA, f"ncbi_{species}.tsv")
    feats, labels, meta = {}, {}, {}
    for row in csv.DictReader(open(path), delimiter="\t"):
        g = row["asm_acc"]
        raw = [t for t in (row["genotypes"] or "").split(";") if t]
        toks = {c for c in (canon(t) for t in raw) if c}
        ph = {}
        for pair in (row["phenotypes"] or "").split(";"):
            if "=" in pair:
                d, _, v = pair.partition("=")
                if v in ("Resistant", "Susceptible"):
                    ph[norm_drug(d)] = 1 if v == "Resistant" else 0
        if not ph:
            continue
        feats[g], labels[g] = toks, ph
        meta[g] = dict(year=row.get("year", ""), geo=row.get("geo", ""),
                       source=row.get("source", ""),
                       clone="|".join(sorted(raw)) or f"solo::{g}")
    return feats, labels, meta


def load_bvbrc(taxon=573):
    """External source. Gene presence only — no mutations available."""
    genes = pd.read_csv(os.path.join(DATA, f"genes_{taxon}.tsv"), sep="\t", dtype=str)
    genes["genome_id"] = genes.genome_id.str.strip('"')
    genes["product"] = genes["product"].fillna("").str.strip('"')
    genes["canon"] = genes["product"].map(canon)
    genes = genes.dropna(subset=["canon"])
    feats = genes.groupby("genome_id")["canon"].apply(set).to_dict()

    amr = pd.read_csv(os.path.join(DATA, f"amr_{taxon}.tsv"), sep="\t", dtype=str)
    for c in ("genome_id", "antibiotic", "resistant_phenotype"):
        amr[c] = amr[c].fillna("").str.strip('"')
    amr = amr[amr.resistant_phenotype.isin(["Resistant", "Susceptible"])]
    amr["drug"] = amr.antibiotic.map(norm_drug)
    labels = defaultdict(dict)
    for g, d, p in zip(amr.genome_id, amr.drug, amr.resistant_phenotype):
        labels[g][d] = 1 if p == "Resistant" else 0

    m = pd.read_csv(os.path.join(DATA, f"meta_{taxon}.tsv"), sep="\t", dtype=str)
    m = m.apply(lambda s: s.str.strip('"') if s.dtype == object else s).set_index("genome_id")
    meta = {g: dict(clone=str(m.loc[g].get("mlst", "") or f"solo::{g}"),
                    year=str(m.loc[g].get("collection_year", "") or ""),
                    geo=str(m.loc[g].get("isolation_country", "") or ""))
            for g in m.index}
    return feats, dict(labels), meta


def build_vocab(feats, ids, lo=PRUNE_LO, hi=PRUNE_HI):
    """Feature columns present in a useful fraction of the cohort."""
    n = len(ids)
    cnt = defaultdict(int)
    for g in ids:
        for t in feats.get(g, ()):
            cnt[t] += 1
    return sorted(t for t, c in cnt.items() if lo * n <= c <= hi * n)


def matrix(feats, ids, vocab):
    vi = {t: i for i, t in enumerate(vocab)}
    X = np.zeros((len(ids), len(vocab)), dtype=np.int8)
    for r, g in enumerate(ids):
        for t in feats.get(g, ()):
            j = vi.get(t)
            if j is not None:
                X[r, j] = 1
    return X


def cohort(feats, labels, drug, min_n=80, min_minority=20):
    """Isolates with a usable label for one drug."""
    ids = [g for g in feats if drug in labels.get(g, {})]
    if len(ids) < min_n:
        return None, None
    y = np.array([labels[g][drug] for g in ids])
    if min(y.sum(), len(y) - y.sum()) < min_minority:
        return None, None
    return ids, y
