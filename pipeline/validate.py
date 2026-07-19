"""Rigorous validation battery.

The prototype reported repeated train_test_split scores and called it evaluation. That measures
how well the model fits one table, not whether it works. This runs five progressively harder
tests, each removing a different crutch:

  1. RANDOM            optimistic baseline — the number most work reports
  2. LINEAGE-AWARE     relatives never straddle the split (MLST sequence type)
  3. LOCKED HOLDOUT    genomes quarantined before any modelling, touched once
  4. EXTERNAL          trained on BV-BRC, tested on NCBI — different curation, different gene
                       caller (AMRFinderPlus), with overlapping isolates removed by accession
  5. TEMPORAL          trained on older isolates, tested on later ones — does it survive the
                       bacteria continuing to evolve after you shipped?

A model that holds up on 4 and 5 is doing biology. One that only holds up on 1 is doing recall.

    python3 pipeline/validate.py

Writes data/validation_report.json
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import canon_bvbrc, canon_ncbi  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
csv.field_size_limit(10 ** 7)

MIN_GENOMES = 400        # per drug, to keep every test adequately powered
MIN_MINORITY = 60        # per drug, smallest class
REPEATS = 10
HOLDOUT_FRAC = 0.20
# Collection years cluster in 2012–2015 (median 2013), so a later cut leaves too few recent
# genomes to measure anything: 2018 yields 28. 2014 splits 2757 older against 491 newer.
TEMPORAL_CUT = 2014

# Abstention band, asymmetric by clinical judgement (see README).
ABSTAIN_LO, ABSTAIN_HI = 0.35, 0.65


def norm_drug(d):
    """'trimethoprim/sulfamethoxazole' and 'trimethoprim-sulfamethoxazole' are one drug."""
    d = (d or "").strip().lower()
    d = d.replace("/", "-").replace(" ", "-")
    d = re.sub(r"-+", "-", d)
    aliases = {
        "trimethoprim-sulphamethoxazole": "trimethoprim-sulfamethoxazole",
        "sulfamethoxazole-trimethoprim": "trimethoprim-sulfamethoxazole",
        "co-trimoxazole": "trimethoprim-sulfamethoxazole",
        "amoxicillin-clavulanic-acid": "amoxicillin-clavulanate",
        "amoxicillin-clavulanate-potassium": "amoxicillin-clavulanate",
        "ticarcillin-clavulanic-acid": "ticarcillin-clavulanate",
        "cephalothin": "cefalotin", "cefalothin": "cefalotin",
        "polymyxin-b": "polymyxin-b",
    }
    return aliases.get(d, d)


def load_bvbrc(taxon=573):
    genes = pd.read_csv(os.path.join(DATA, f"genes_{taxon}.tsv"), sep="\t", dtype=str)
    genes["genome_id"] = genes.genome_id.str.strip('"')
    genes["product"] = genes["product"].fillna("").str.strip('"')
    genes["canon"] = genes["product"].map(canon_bvbrc)
    genes = genes.dropna(subset=["canon"])
    feats = genes.groupby("genome_id")["canon"].apply(set).to_dict()

    amr = pd.read_csv(os.path.join(DATA, f"amr_{taxon}.tsv"), sep="\t", dtype=str)
    for c in ("genome_id", "antibiotic", "resistant_phenotype"):
        amr[c] = amr[c].fillna("").str.strip('"')
    amr = amr[amr.resistant_phenotype.isin(["Resistant", "Susceptible"])]
    amr["drug"] = amr.antibiotic.map(norm_drug)
    labels = defaultdict(dict)
    for gid, d, p in zip(amr.genome_id, amr.drug, amr.resistant_phenotype):
        labels[gid][d] = 1 if p == "Resistant" else 0

    meta = pd.read_csv(os.path.join(DATA, f"meta_{taxon}.tsv"), sep="\t", dtype=str)
    meta = meta.apply(lambda s: s.str.strip('"') if s.dtype == object else s)
    meta = meta.set_index("genome_id")
    return feats, labels, meta


def load_ncbi(species="klebsiella", exclude_acc=frozenset(), exclude_sra=frozenset()):
    """External set, with anything sharing an accession with BV-BRC removed."""
    path = os.path.join(DATA, f"ncbi_{species}.tsv")
    if not os.path.exists(path):
        return {}, {}, {}
    acc_map = {}
    raw = os.path.join(DATA, "ncbi_amr_kleb.tsv")
    if os.path.exists(raw):
        rd = csv.reader(open(raw, newline="", encoding="utf-8", errors="replace"), delimiter="\t")
        h = next(rd)
        iA, iR, iP = h.index("asm_acc"), h.index("Run"), h.index("AST_phenotypes")
        for r in rd:
            if len(r) > iP and r[iP] and r[iP] not in ("NULL", "-") and r[iA]:
                acc_map[r[iA]] = set(x for x in (r[iR] or "").split(",") if x)

    feats, labels, meta, dropped = {}, {}, {}, 0
    for row in csv.DictReader(open(path), delimiter="\t"):
        acc = row["asm_acc"]
        base = acc.split(".")[0]
        runs = acc_map.get(acc, set())
        if base in exclude_acc or (runs & exclude_sra):
            dropped += 1
            continue
        toks = {canon_ncbi(t) for t in (row["genotypes"] or "").split(";") if t}
        toks.discard(None)
        ph = {}
        for pair in (row["phenotypes"] or "").split(";"):
            if "=" in pair:
                d, _, v = pair.partition("=")
                if v in ("Resistant", "Susceptible"):
                    ph[norm_drug(d)] = 1 if v == "Resistant" else 0
        if not ph:
            continue
        feats[acc], labels[acc] = toks, ph
        meta[acc] = dict(year=row.get("year", ""), geo=row.get("geo", ""),
                         source=row.get("source", ""))
    print(f"   NCBI external: {len(feats)} isolates ({dropped} dropped as overlapping BV-BRC)")
    return feats, labels, meta


def matrix(feats, ids, vocab):
    v = {t: i for i, t in enumerate(vocab)}
    X = np.zeros((len(ids), len(vocab)), dtype=np.int8)
    for r, g in enumerate(ids):
        for t in feats.get(g, ()):
            j = v.get(t)
            if j is not None:
                X[r, j] = 1
    return X


def fit(X, y):
    return CalibratedClassifierCV(
        HistGradientBoostingClassifier(max_iter=250, random_state=0),
        method="isotonic", cv=3).fit(X, y)


def score(m, X, y):
    if len(np.unique(y)) < 2:
        return None, None
    p = m.predict_proba(X)[:, 1]
    return roc_auc_score(y, p), brier_score_loss(y, p)


def main():
    print("1. loading BV-BRC (training source) ...")
    feats, labels, meta = load_bvbrc(573)
    print(f"   {len(feats)} genomes with harmonized features")

    acc = pd.read_csv(os.path.join(DATA, "bvbrc_accessions.tsv"), sep="\t", dtype=str) \
        if os.path.exists(os.path.join(DATA, "bvbrc_accessions.tsv")) else pd.DataFrame()
    ex_acc = set(acc.assembly_accession.dropna().str.split(".").str[0]) if len(acc) else set()
    ex_sra = set(acc.sra_accession.dropna()) if len(acc) else set()

    print("2. loading NCBI (external source) ...")
    nfeats, nlabels, nmeta = load_ncbi("klebsiella", ex_acc, ex_sra)

    vocab = sorted({t for s in feats.values() for t in s} |
                   {t for s in nfeats.values() for t in s})
    print(f"3. shared vocabulary: {len(vocab)} canonical resistance tokens")

    # Quarantine by lineage before anything else touches the data.
    gids = sorted(g for g in feats if g in labels)
    lin = meta.reindex(gids)["mlst"].fillna("").replace("nan", "").values
    lin = np.array([l if l else f"__solo_{i}" for i, l in enumerate(lin)])
    tr_i, ho_i = next(GroupShuffleSplit(n_splits=1, test_size=HOLDOUT_FRAC,
                                        random_state=1234).split(gids, groups=lin))
    train_ids = [gids[i] for i in tr_i]
    hold_ids = [gids[i] for i in ho_i]
    print(f"4. locked holdout: {len(train_ids)} train / {len(hold_ids)} quarantined genomes")
    json.dump({"train": train_ids, "holdout": hold_ids},
              open(os.path.join(DATA, "split.json"), "w"))

    drugs = sorted({d for g in train_ids for d in labels[g]})
    report, rows = {}, []
    for drug in drugs:
        tr = [g for g in train_ids if drug in labels[g]]
        ho = [g for g in hold_ids if drug in labels[g]]
        if len(tr) < MIN_GENOMES:
            continue
        ytr = np.array([labels[g][drug] for g in tr])
        if min(ytr.sum(), len(ytr) - ytr.sum()) < MIN_MINORITY:
            continue
        Xtr = matrix(feats, tr, vocab)
        gtr = meta.reindex(tr)["mlst"].fillna("").values
        gtr = np.array([l if l else f"__s{i}" for i, l in enumerate(gtr)])

        # 1 + 2: random vs lineage-aware, repeated
        rnd, lng = [], []
        for s in range(REPEATS):
            a, b = train_test_split(np.arange(len(ytr)), test_size=.3,
                                    random_state=s, stratify=ytr)
            m = HistGradientBoostingClassifier(max_iter=250, random_state=0).fit(Xtr[a], ytr[a])
            if len(np.unique(ytr[b])) > 1:
                rnd.append(roc_auc_score(ytr[b], m.predict_proba(Xtr[b])[:, 1]))
            a2, b2 = next(GroupShuffleSplit(n_splits=1, test_size=.3,
                                            random_state=s).split(Xtr, ytr, groups=gtr))
            if len(np.unique(ytr[b2])) > 1:
                m2 = HistGradientBoostingClassifier(max_iter=250, random_state=0).fit(Xtr[a2], ytr[a2])
                lng.append(roc_auc_score(ytr[b2], m2.predict_proba(Xtr[b2])[:, 1]))

        model = fit(Xtr, ytr)

        # 3: locked holdout — first and only use
        ho_auc = ho_br = None
        if len(ho) >= 40:
            yho = np.array([labels[g][drug] for g in ho])
            ho_auc, ho_br = score(model, matrix(feats, ho, vocab), yho)

        # 4: external — NCBI, different curation and gene caller
        ext_auc = ext_n = None
        nids = [a for a in nfeats if drug in nlabels.get(a, {})]
        if len(nids) >= 40:
            yn = np.array([nlabels[a][drug] for a in nids])
            if len(np.unique(yn)) > 1:
                ext_auc, _ = score(model, matrix(nfeats, nids, vocab), yn)
                ext_n = len(nids)

        # 5: temporal — train on the past, test on the future
        tmp_auc = tmp_n = None
        # Undated genomes are excluded outright. Coercing them to year 0 would silently pile
        # every one of them into the "past" group and quietly corrupt the comparison.
        yr = pd.to_numeric(meta.reindex(tr)["collection_year"], errors="coerce").values
        dated = ~np.isnan(yr)
        old = np.where(dated & (yr <= TEMPORAL_CUT))[0]
        new = np.where(dated & (yr > TEMPORAL_CUT))[0]
        if len(old) >= 200 and len(new) >= 40 and len(np.unique(ytr[new])) > 1 \
                and min(ytr[old].sum(), len(old) - ytr[old].sum()) >= 20:
            mt = HistGradientBoostingClassifier(max_iter=250, random_state=0).fit(Xtr[old], ytr[old])
            tmp_auc = roc_auc_score(ytr[new], mt.predict_proba(Xtr[new])[:, 1])
            tmp_n = len(new)

        report[drug] = dict(
            n_train=len(tr), pct_resistant=round(100 * float(ytr.mean())),
            random=round(float(np.mean(rnd)), 3) if rnd else None,
            random_sd=round(float(np.std(rnd)), 3) if rnd else None,
            lineage=round(float(np.mean(lng)), 3) if lng else None,
            lineage_sd=round(float(np.std(lng)), 3) if lng else None,
            holdout=round(float(ho_auc), 3) if ho_auc else None, n_holdout=len(ho),
            external=round(float(ext_auc), 3) if ext_auc else None, n_external=ext_n,
            temporal=round(float(tmp_auc), 3) if tmp_auc else None, n_temporal=tmp_n,
            brier=round(float(ho_br), 3) if ho_br else None)
        rows.append(drug)
        r = report[drug]
        print(f"   {drug:<32} n={r['n_train']:>5} "
              f"rand {r['random'] or 0:.3f} | lin {r['lineage'] or 0:.3f} | "
              f"hold {r['holdout'] or 0:.3f} | ext {r['external'] or 0:.3f} | "
              f"temp {r['temporal'] or 0:.3f}")

    def avg(k):
        v = [r[k] for r in report.values() if r.get(k)]
        return round(float(np.mean(v)), 3) if v else None

    summary = dict(
        drugs=len(report), vocabulary=len(vocab),
        genomes_train=len(train_ids), genomes_holdout=len(hold_ids),
        external_isolates=len(nfeats),
        mean=dict(random=avg("random"), lineage=avg("lineage"), holdout=avg("holdout"),
                  external=avg("external"), temporal=avg("temporal")))
    json.dump(dict(summary=summary, per_drug=report),
              open(os.path.join(DATA, "validation_report.json"), "w"), indent=1)

    print("\n" + "=" * 72)
    print("MEAN AUC ACROSS", len(report), "ANTIBIOTICS")
    print("=" * 72)
    for k, lbl in [("random", "1. random split (optimistic baseline)"),
                   ("lineage", "2. lineage-aware split"),
                   ("holdout", "3. locked holdout (never seen)"),
                   ("external", "4. EXTERNAL — NCBI, different curation + gene caller"),
                   ("temporal", f"5. temporal — train <={TEMPORAL_CUT}, test after")]:
        v = summary["mean"][k]
        print(f"   {lbl:<52} {v if v else 'n/a'}")
    print(f"\nwrote {os.path.join(DATA, 'validation_report.json')}")


if __name__ == "__main__":
    main()
