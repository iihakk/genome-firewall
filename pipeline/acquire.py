"""Full-scale data acquisition.

Replaces the 600-genome prototype sample with the complete laboratory-confirmed record for
multiple species, plus the metadata needed for lineage-, time- and source-aware validation.

    python3 pipeline/acquire.py

Writes to data/: amr_<taxon>.tsv, genes_<taxon>.tsv, meta_<taxon>.tsv

Notes on the API that cost time to discover:
  * hard cap of 25,000 rows per response — everything must paginate via limit(count,start)
  * spaces must be %20-encoded or queries fail silently with an empty body
  * the `gene` field is ~1% populated; `product` is the usable feature vocabulary
  * evidence must be filtered to "Laboratory Method" — the bulk of rows are another model's
    predictions, and training on those teaches imitation rather than biology
"""

import csv
import io
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
API = "https://www.bv-brc.org/api"
PAGE = 25000

SPECIES = {
    573: "klebsiella_pneumoniae",
    562: "escherichia_coli",
    1280: "staphylococcus_aureus",
    470: "acinetobacter_baumannii",
}

_print_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(*a, flush=True)


def get(url, timeout=180, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode()
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def rows(url):
    txt = get(url)
    rd = csv.reader(io.StringIO(txt), delimiter="\t")
    hdr = next(rd, None)
    return hdr, [r for r in rd]


def paginate(base, select, cap=None):
    """Walk limit(count,start) until a short page comes back."""
    out, hdr, start = [], None, 0
    while True:
        url = f"{base}&select({select})&limit({PAGE},{start})&http_accept=text/tsv"
        h, rs = rows(url)
        hdr = hdr or h
        out += rs
        if len(rs) < PAGE or (cap and len(out) >= cap):
            break
        start += PAGE
    return hdr, out


def fetch_amr(taxon):
    base = (f"{API}/genome_amr/?and(eq(taxon_id,{taxon}),"
            f"eq(evidence,%22Laboratory%20Method%22))")
    sel = ("genome_id,genome_name,antibiotic,resistant_phenotype,measurement,"
           "measurement_unit,laboratory_typing_method,testing_standard")
    hdr, rs = paginate(base, sel)
    log(f"  [{taxon}] AMR rows: {len(rs)}")
    return hdr, rs


def fetch_meta(taxon, gids):
    sel = ("genome_id,genome_name,mlst,isolation_source,isolation_country,"
           "collection_year,host_name,genome_length,genome_status,contigs")
    out, hdr = [], None
    def one(chunk):
        ids = ",".join(chunk)
        url = f"{API}/genome/?in(genome_id,({ids}))&select({sel})&limit(5000)&http_accept=text/tsv"
        try:
            return rows(url)
        except Exception as e:
            log(f"    meta chunk failed: {repr(e)[:60]}")
            return None, []
    chunks = [gids[i:i + 100] for i in range(0, len(gids), 100)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        for h, rs in ex.map(one, chunks):
            hdr = hdr or h
            out += rs
    log(f"  [{taxon}] metadata rows: {len(out)}")
    return hdr, out


def fetch_genes(taxon, gids, batch=60):
    """Resistance-gene annotations per genome. This is the slow leg — parallelise it."""
    out, hdr, done = [], None, [0]
    def one(chunk):
        ids = ",".join(chunk)
        url = (f"{API}/sp_gene/?and(in(genome_id,({ids})),"
               f"eq(property,%22Antibiotic%20Resistance%22))"
               f"&select(genome_id,product,gene,classification)&limit(25000)&http_accept=text/tsv")
        try:
            h, rs = rows(url)
        except Exception as e:
            log(f"    gene chunk failed: {repr(e)[:60]}")
            return None, []
        done[0] += len(chunk)
        if done[0] % 600 < batch:
            log(f"    ... {done[0]}/{len(gids)} genomes")
        return h, rs
    chunks = [gids[i:i + batch] for i in range(0, len(gids), batch)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        for h, rs in ex.map(one, chunks):
            hdr = hdr or h
            out += rs
    log(f"  [{taxon}] gene annotation rows: {len(out)}")
    return hdr, out


def write(path, hdr, rs):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        if hdr:
            w.writerow(hdr)
        w.writerows(rs)


def main(taxa):
    os.makedirs(DATA, exist_ok=True)
    for taxon in taxa:
        name = SPECIES.get(taxon, str(taxon))
        log(f"\n=== {name} ({taxon}) ===")
        t0 = time.time()

        hdr, amr = fetch_amr(taxon)
        write(os.path.join(DATA, f"amr_{taxon}.tsv"), hdr, amr)
        gi = hdr.index("genome_id") if hdr and "genome_id" in hdr else 0
        gids = sorted({r[gi].strip('"') for r in amr if len(r) > gi and r[gi].strip('"')})
        log(f"  [{taxon}] distinct genomes: {len(gids)}")

        h, meta = fetch_meta(taxon, gids)
        write(os.path.join(DATA, f"meta_{taxon}.tsv"), h, meta)

        h, genes = fetch_genes(taxon, gids)
        write(os.path.join(DATA, f"genes_{taxon}.tsv"), h, genes)
        log(f"  [{taxon}] done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    arg = sys.argv[1:] or ["573", "562"]
    main([int(a) for a in arg])
