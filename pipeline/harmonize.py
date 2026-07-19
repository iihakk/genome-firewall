"""Map BV-BRC product descriptions and NCBI/AMRFinderPlus gene symbols into one vocabulary.

Without this the two sources cannot be compared, and external validation is impossible: BV-BRC
writes "Class A beta-lactamase (EC 3.5.2.6) => KPC family, carbapenem-hydrolyzing" where NCBI
writes "blaKPC-2". Same enzyme, different string.

The canonical form is a resistance *family*, not an allele. blaKPC-2 and blaKPC-3 collapse to
blaKPC deliberately: allele-level features explode the space, and — as measured in
VALIDATION_FINDINGS.md — near-identical variants scattered across a random split are exactly what
inflates apparent accuracy. Families generalise; alleles memorise.

Point mutations and truncations are kept as separate token types because they are distinct
mechanisms, not variants of a gene call.
"""

import re

# Ordered: first match wins, so specific patterns must precede general ones
# (OXA-48 carbapenemase before generic OXA, for instance).
RULES = [
    # ── beta-lactamases ────────────────────────────────────────────────────────
    (r"KPC", "blaKPC"),
    (r"\bNDM\b|New Delhi", "blaNDM"),
    (r"\bVIM\b", "blaVIM"),
    (r"\bIMP-|\bIMP\b.*metallo", "blaIMP"),
    (r"OXA-?48|OXA-?181|OXA-?232", "blaOXA-48"),
    (r"OXA-?23|OXA-?24|OXA-?40|OXA-?58|OXA-?51|OXA-?143", "blaOXA-carbapenemase"),
    (r"CTX-?M", "blaCTX-M"),
    (r"\bTEM\b", "blaTEM"),
    (r"\bSHV\b", "blaSHV"),
    (r"\bGES\b", "blaGES"),
    (r"\bPER\b", "blaPER"),
    (r"\bVEB\b", "blaVEB"),
    (r"\bCMY\b|\bDHA\b|\bFOX\b|\bACT\b|\bMIR\b|AmpC", "blaAmpC"),
    (r"\bOXA\b|oxacillinase", "blaOXA"),
    (r"beta-?lactamase", "beta_lactamase_other"),

    # ── aminoglycosides ────────────────────────────────────────────────────────
    (r"aac\(6'\)|N\(6'\)-acetyltransferase", "aac(6')"),
    (r"aac\(3\)|N\(3\)-acetyltransferase", "aac(3)"),
    (r"aac\(2'\)", "aac(2')"),
    (r"aph\(3''\)|3''-phosphotransferase", "aph(3'')"),
    (r"aph\(3'\)|3'-phosphotransferase", "aph(3')"),
    (r"aph\(6\)|6-phosphotransferase", "aph(6)"),
    (r"ant\(3''\)|3''-nucleotidyltransferase|aadA", "ant(3'')"),
    (r"ant\(2''\)|2''-nucleotidyltransferase", "ant(2'')"),
    (r"\barmA\b|\brmt[A-Z]\b|16S rRNA.*methyltransferase", "rmt_16S_methylase"),
    (r"aminoglycoside", "aminoglycoside_other"),

    # ── quinolones ─────────────────────────────────────────────────────────────
    (r"qnrA", "qnrA"), (r"qnrB", "qnrB"), (r"qnrS", "qnrS"),
    (r"\bqnr", "qnr_other"),
    (r"quinolone", "quinolone_other"),

    # ── other classes ──────────────────────────────────────────────────────────
    (r"\bsul\d|dihydropteroate|sulfonamide", "sul"),
    (r"\bdfr[A-Z]|dihydrofolate|trimethoprim", "dfr"),
    (r"\btet\(|tetracycline", "tet"),
    (r"\bmph\(|macrolide.*phosphotransferase", "mph"),
    (r"\berm\(|\bermB|rRNA.*methyl.*erythromycin", "erm"),
    (r"\bmef\(", "mef"),
    (r"\bcat[AB]?\b|chloramphenicol", "cat"),
    (r"\bfloR\b|florfenicol", "floR"),
    (r"\bfosA|fosfomycin", "fosA"),
    (r"\bmcr-?\d|colistin", "mcr"),
    (r"\bvan[ABCDEGM]\b|vancomycin", "van"),
    (r"\bqac[E]?|quaternary ammonium", "qac"),
    (r"\bmecA\b|\bmecC\b", "mecA"),
]

# Chromosomal targets whose mutation or loss confers resistance. AMRFinderPlus reports these as
# POINT / truncation calls; BV-BRC's gene-presence view largely cannot see them, which is one of
# the concrete reasons the NCBI feature set is richer.
TARGETS = [
    (r"gyrA", "gyrA"), (r"gyrB", "gyrB"), (r"parC", "parC"), (r"parE", "parE"),
    (r"ompK35", "ompK35"), (r"ompK36", "ompK36"), (r"ompK37", "ompK37"),
    (r"rpoB", "rpoB"), (r"pmrB", "pmrB"), (r"phoQ", "phoQ"), (r"mgrB", "mgrB"),
    (r"crrB", "crrB"), (r"ramR", "ramR"), (r"acrR", "acrR"), (r"marR", "marR"),
    (r"folP", "folP"), (r"rrs", "rrs"), (r"katG", "katG"),
]


def _match(text, rules):
    for pat, canon in rules:
        if re.search(pat, text, re.I):
            return canon
    return None


def canon_bvbrc(product: str):
    """BV-BRC product description -> canonical family token, or None if not resistance-relevant."""
    if not product:
        return None
    hit = _match(product, RULES)
    if hit:
        return hit
    tgt = _match(product, TARGETS)
    # A bare target gene with no mutation call is just the wild-type gene — not evidence of
    # resistance. Dropping it avoids teaching the model that "has gyrA" means anything.
    return None if tgt else None


def canon_ncbi(token: str):
    """AMRFinderPlus token -> canonical form.

    Handles the three token shapes emitted by ncbi_extract.parse_geno:
        blaKPC              acquired gene
        POINT:gyrA_S83I     target mutation
        TRUNC:ompK35        target truncation / porin loss
    """
    if not token:
        return None
    if token.startswith("POINT:"):
        body = token[6:]
        gene = _match(body, TARGETS)
        return f"POINT:{gene}" if gene else None
    if token.startswith("TRUNC:"):
        body = token[6:]
        gene = _match(body, TARGETS)
        return f"TRUNC:{gene}" if gene else None
    return _match(token, RULES)


def vector(tokens):
    """Canonical token set from an iterable of raw source strings (either source)."""
    out = set()
    for t in tokens:
        c = canon_ncbi(t) if (t.startswith(("POINT:", "TRUNC:")) or len(t) < 30) else canon_bvbrc(t)
        if c:
            out.add(c)
    return out


if __name__ == "__main__":
    bv = [
        "Class A beta-lactamase (EC 3.5.2.6) => KPC family, carbapenem-hydrolyzing",
        "Class A beta-lactamase (EC 3.5.2.6) => CTX-M family, extended-spectrum",
        "Aminoglycoside N(6')-acetyltransferase (EC 2.3.1.82) => AAC(6')-Ib/AAC(6')-II",
        "Pentapeptide repeat protein QnrB family => Quinolone resistance protein QnrB10",
        "Dihydropteroate synthase type-2 (EC 2.5.1.15) @ Sulfonamide resistance protein",
        "Chromosome (plasmid) partitioning protein ParA",
    ]
    nc = ["blaKPC", "blaCTX-M", "aac(6')-Ib", "qnrB", "sul1",
          "POINT:gyrA_S83I", "TRUNC:ompK35", "fosA"]
    print("BV-BRC -> canonical")
    for p in bv:
        print(f"   {(canon_bvbrc(p) or '(dropped)'):<24} {p[:62]}")
    print("\nNCBI -> canonical")
    for t in nc:
        print(f"   {(canon_ncbi(t) or '(dropped)'):<24} {t}")
    shared = {canon_bvbrc(p) for p in bv} & {canon_ncbi(t) for t in nc}
    print(f"\nshared vocabulary in this sample: {sorted(x for x in shared if x)}")
