"""Extract an INDEPENDENT validation set from NCBI Pathogen Detection.

BV-BRC and NCBI are separate curations. Training on BV-BRC and testing on NCBI is therefore a
genuine external validation — different submitters, different curation pipeline, different gene
caller — rather than another resample of the same table.

NCBI's AMR_genotypes come from AMRFinderPlus (the tool the challenge brief names as its default)
and are richer than BV-BRC's gene lists in two ways that matter clinically:

  * point mutations   gyrA_S83I=POINT      fluoroquinolone target change
  * truncations       ompK35_E42RfsTer     porin loss — a real carbapenem mechanism

Neither is representable in a plain "which genes are present" vector, which is part of why the
prototype's feature space was too thin.

    python3 pipeline/ncbi_extract.py <species>

Writes data/ncbi_<species>.tsv with one row per isolate:
    asm_acc, collection_year, geo, source, drug=phenotype pairs, genotype tokens
"""

import csv
import os
import re
import sys

csv.field_size_limit(10 ** 7)
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# NCBI reports S / I / R plus some verbose variants; collapse to the binary clinical question,
# dropping intermediates rather than guessing which side they fall on.
PHEN = {
    "S": "Susceptible", "susceptible": "Susceptible",
    "R": "Resistant", "resistant": "Resistant",
    "I": "Intermediate", "intermediate": "Intermediate",
    "SDD": "Intermediate", "nonsusceptible": "Resistant",
}


def parse_ast(cell):
    """'amikacin=I,aztreonam=R,...' -> {'amikacin': 'Intermediate', ...}"""
    out = {}
    for part in cell.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        drug, _, val = part.partition("=")
        val = val.strip().split("|")[0]
        p = PHEN.get(val) or PHEN.get(val.lower())
        if p:
            out[drug.strip().lower()] = p
    return out


def parse_geno(cell):
    """'aac(6')-Ib,blaKPC-2,gyrA_S83I=POINT' -> normalised token list.

    Variant suffixes are stripped (blaKPC-2 -> blaKPC) so the feature space generalises across
    variants instead of exploding into one column per allele. Point mutations and truncations are
    kept as their own tokens because they are distinct mechanisms, not variants of a gene call.
    """
    toks = []
    for part in cell.split(","):
        part = part.strip()
        if not part or part.upper() in ("NULL", "-"):
            continue
        if part.endswith("=MISTRANSLATION") or part.endswith("=PARTIAL"):
            continue
        if part.endswith("=POINT"):
            toks.append("POINT:" + part[:-6])
            continue
        if re.search(r"fsTer|Ter\d*$", part):
            toks.append("TRUNC:" + re.split(r"_", part)[0])
            continue
        base = re.sub(r"-\d+$", "", part)          # blaKPC-2 -> blaKPC
        base = re.sub(r"=.*$", "", base)
        toks.append(base)
    return sorted(set(toks))


def main(species="Klebsiella"):
    src = os.path.join(DATA, f"ncbi_amr_{species.lower()[:4]}.tsv")
    if not os.path.exists(src):
        sys.exit(f"missing {src} — download it first")

    f = open(src, newline="", encoding="utf-8", errors="replace")
    rd = csv.reader(f, delimiter="\t")
    hdr = next(rd)
    idx = {k: hdr.index(k) for k in
           ("asm_acc", "AST_phenotypes", "AMR_genotypes", "collection_date",
            "geo_loc_name", "isolation_source", "scientific_name")}

    out, n, drugs = [], 0, {}
    for r in rd:
        n += 1
        if len(r) <= idx["AST_phenotypes"]:
            continue
        ast = r[idx["AST_phenotypes"]]
        if not ast or ast in ("NULL", "-"):
            continue
        phen = parse_ast(ast)
        if not phen:
            continue
        geno = parse_geno(r[idx["AMR_genotypes"]] if len(r) > idx["AMR_genotypes"] else "")
        yr = ""
        m = re.search(r"(19|20)\d{2}", r[idx["collection_date"]] or "")
        if m:
            yr = m.group(0)
        for d in phen:
            drugs[d] = drugs.get(d, 0) + 1
        out.append(dict(
            asm_acc=r[idx["asm_acc"]],
            year=yr,
            geo=(r[idx["geo_loc_name"]] or "").split(":")[0],
            source=(r[idx["isolation_source"]] or "").lower()[:40],
            organism=r[idx["scientific_name"]],
            phenotypes=";".join(f"{k}={v}" for k, v in sorted(phen.items())),
            genotypes=";".join(geno),
            n_genes=len(geno)))

    dest = os.path.join(DATA, f"ncbi_{species.lower()}.tsv")
    with open(dest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), delimiter="\t")
        w.writeheader()
        w.writerows(out)

    print(f"scanned {n} isolates -> {len(out)} with AST phenotypes")
    print(f"wrote {dest}")
    print(f"\ndrugs with >=100 tested isolates:")
    for d, c in sorted(drugs.items(), key=lambda x: -x[1]):
        if c >= 100:
            print(f"   {d:<34} {c}")
    yrs = [o["year"] for o in out if o["year"]]
    if yrs:
        print(f"\ncollection years: {min(yrs)}–{max(yrs)}  ({len(yrs)} dated)")
    print(f"mean AMR genotype tokens per isolate: {sum(o['n_genes'] for o in out)/len(out):.1f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Klebsiella")
