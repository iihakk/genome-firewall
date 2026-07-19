"""LLM-based resistance-annotation normalisation.

Replaces the hand-written regex in harmonize.py, which covered only 24% of distinct BV-BRC
products and — as we discovered by auditing it — silently discarded blaSHV, blaTEM and blaOXA
through a word-boundary error, plus oqxA/oqxB which were never encoded at all. Roughly 7,000
feature occurrences were being thrown away.

Regex is brittle in exactly that way, and it cannot classify a string it was not written for. A
model can, which matters at inference time when a genome carries an annotation absent from every
rule we thought to write.

Each distinct annotation string is classified once and cached, so this costs a few cents total and
nothing on re-runs. The output is a structured record per string:

    family      canonical resistance family, or null if not a determinant
    kind        acquired_gene | point_mutation | truncation | efflux | regulator | target
    drugs       antibiotic classes plausibly affected
    confidence  0-1, used to gate low-confidence assignments out of the feature space

    python3 pipeline/llm_harmonize.py

Writes data/vocab_map.json
"""

import csv
import json
import os
import sys
import time
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from harmonize import canon_bvbrc, canon_ncbi  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
csv.field_size_limit(10 ** 7)

MODEL = "gpt-4o-mini"
BATCH = 40
CACHE = os.path.join(DATA, "vocab_map.json")

SYSTEM = """You are a clinical microbiology expert normalising antimicrobial resistance gene \
annotations into a controlled vocabulary.

For each annotation string, decide whether it denotes a determinant that contributes to \
antibiotic resistance in Gram-negative bacteria, and if so classify it.

Rules:
- `family` must be a stable canonical name for the resistance FAMILY, not the allele. Collapse \
variants: blaKPC-2, blaKPC-3 and "KPC family carbapenem-hydrolyzing" are all `blaKPC`. Use the \
conventional gene-family name (blaKPC, blaCTX-M, blaSHV, blaTEM, blaNDM, blaOXA-48, aac(6'), \
aac(3), aph(3'), qnrB, sul, dfr, tet, mph, catA, oqxAB, mcr, fosA, acrAB, mdfA, emrAB, marA ...).
- Housekeeping genes and generic cellular machinery are NOT determinants. "Translation elongation \
factor Tu" is a drug target but not a resistance determinant: return family null.
- Efflux pumps and resistance regulators ARE determinants (kind `efflux` / `regulator`) even when \
chromosomal and common.
- `kind`: acquired_gene, point_mutation, truncation, efflux, regulator, or target.
- Tokens prefixed POINT: denote a target mutation; TRUNC: denotes gene truncation/loss.
- `drugs`: antibiotic classes plausibly affected, lowercase (e.g. carbapenem, cephalosporin, \
penicillin, fluoroquinolone, aminoglycoside, sulfonamide, trimethoprim, tetracycline, macrolide, \
phenicol, polymyxin, fosfomycin). Empty list if none or unknown.
- `confidence`: your certainty in the family assignment, 0 to 1. Be honest; low confidence is \
more useful to us than a confident guess."""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "family": {"type": ["string", "null"]},
                    "kind": {"type": ["string", "null"]},
                    "drugs": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["input", "family", "kind", "drugs", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def client():
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        env = os.path.join(HERE, ".env")
        if os.path.exists(env):
            for line in open(env):
                if line.startswith("OPENAI_API_KEY"):
                    key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("no OPENAI_API_KEY in environment or .env")
    return OpenAI(api_key=key)


def collect_strings():
    """Every distinct annotation string across both sources."""
    seen = Counter()
    g = os.path.join(DATA, "genes_573.tsv")
    if os.path.exists(g):
        df = pd.read_csv(g, sep="\t", dtype=str)
        for p, c in Counter(df["product"].fillna("").str.strip('"')).items():
            if p:
                seen[p] += c
    n = os.path.join(DATA, "ncbi_klebsiella.tsv")
    if os.path.exists(n):
        for row in csv.DictReader(open(n), delimiter="\t"):
            for t in (row["genotypes"] or "").split(";"):
                if t:
                    seen[t] += 1
    return seen


def classify(cl, strings):
    msg = ("Classify each annotation. Return one item per input, preserving the exact input "
           "string.\n\n" + "\n".join(f"- {s}" for s in strings))
    r = cl.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "annotations", "strict": True,
                                         "schema": SCHEMA}})
    return json.loads(r.choices[0].message.content)["items"]


def main():
    strings = collect_strings()
    print(f"distinct annotation strings across both sources: {len(strings)}")

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [s for s in strings if s not in cache]
    print(f"cached: {len(cache)} | to classify: {len(todo)}")

    if todo:
        cl = client()
        t0 = time.time()
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            try:
                for item in classify(cl, chunk):
                    cache[item["input"]] = item
            except Exception as e:
                print(f"  batch {i} failed: {repr(e)[:90]}")
                continue
            done = min(i + BATCH, len(todo))
            print(f"  {done}/{len(todo)}  ({time.time()-t0:.0f}s)", flush=True)
            json.dump(cache, open(CACHE, "w"), indent=1)
    json.dump(cache, open(CACHE, "w"), indent=1)

    # How much did we recover over the regex we are replacing?
    det = {s: v for s, v in cache.items() if v.get("family") and v.get("confidence", 0) >= 0.5}
    regex_hit = sum(1 for s in strings if (canon_ncbi(s) if len(s) < 30 else canon_bvbrc(s)))
    rows_total = sum(strings.values())
    rows_llm = sum(strings[s] for s in det if s in strings)
    rows_regex = sum(c for s, c in strings.items()
                     if (canon_ncbi(s) if len(s) < 30 else canon_bvbrc(s)))

    print(f"\n{'':<22}{'distinct':>10}{'rows':>12}")
    print("-" * 44)
    print(f"{'regex (old)':<22}{regex_hit:>10}{rows_regex:>12}")
    print(f"{'LLM (new)':<22}{len(det):>10}{rows_llm:>12}")
    print(f"{'total strings':<22}{len(strings):>10}{rows_total:>12}")
    print(f"\ncoverage: regex {100*regex_hit/len(strings):.0f}% of distinct, "
          f"{100*rows_regex/rows_total:.0f}% of rows")
    print(f"          LLM   {100*len(det)/len(strings):.0f}% of distinct, "
          f"{100*rows_llm/rows_total:.0f}% of rows")

    print(f"\ncanonical families discovered: {len(set(v['family'] for v in det.values()))}")
    print("\nrecovered determinants the regex missed (top 15 by frequency):")
    missed = [(strings[s], s, det[s]["family"], det[s]["kind"]) for s in det
              if not (canon_ncbi(s) if len(s) < 30 else canon_bvbrc(s))]
    for c, s, fam, kind in sorted(missed, reverse=True)[:15]:
        print(f"   {c:>7}  {fam:<14} {kind:<14} {s[:52]}")
    print(f"\nwrote {CACHE}")


if __name__ == "__main__":
    main()
