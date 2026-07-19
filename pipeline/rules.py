"""Clinical genotype-to-phenotype rules — the baseline we have to justify replacing.

This is what a ResFinder + PointFinder style lookup does: if a known determinant is present,
call resistance. Every accuracy claim we make is stated against this, because it is the
alternative a clinical laboratory already has.

Specification matters more than it looks. An earlier version of this file included blaSHV in the
cephalosporin rules. blaSHV is CHROMOSOMAL in Klebsiella pneumoniae and present in 92% of
isolates, so the rule fired on almost every genome, scored 0.49 — barely above chance — and
inflated our apparent advantage from +0.047 to +0.165. A baseline you have accidentally crippled
flatters you and will not survive a reviewer. blaSHV and blaTEM are excluded below because
neither marks extended-spectrum activity without allele-level typing, which we do not do.
"""

CARBAPENEMASE = {"blakpc", "blandm", "blavim", "blaimp", "blaoxa-48", "blaoxa48"}

# Extended-spectrum only. Wild-type SHV/TEM deliberately excluded — see module docstring.
ESBL = {"blactx-m", "blactxm", "blaper", "blaveb", "blages"}

AMPC = {"blaampc", "blacmy", "bladha", "blafox", "blaact", "blamir"}

# Porin loss raises carbapenem MICs when combined with a beta-lactamase; on its own it is
# usually insufficient, but ertapenem is the most sensitive to it.
PORIN = {"TRUNC:ompk35", "TRUNC:ompk36", "POINT:ompk35", "POINT:ompk36"}

FLUOROQUINOLONE = {"POINT:gyra", "POINT:parc", "POINT:gyrb", "POINT:pare",
                   "qnra", "qnrb", "qnrs", "qnr", "oqxab"}

AMINOGLYCOSIDE_16S = {"rmt", "arma", "npma"}

COLISTIN = {"mcr", "TRUNC:mgrb", "POINT:mgrb", "POINT:pmrb", "POINT:phoq", "POINT:pmra"}

RULES = {
    "meropenem": CARBAPENEMASE,
    "imipenem": CARBAPENEMASE,
    "ertapenem": CARBAPENEMASE | PORIN,
    "doripenem": CARBAPENEMASE,

    "ceftazidime": CARBAPENEMASE | ESBL | AMPC,
    "ceftriaxone": CARBAPENEMASE | ESBL | AMPC,
    "cefotaxime": CARBAPENEMASE | ESBL | AMPC,
    "cefepime": CARBAPENEMASE | ESBL,
    "cefoxitin": AMPC | CARBAPENEMASE,
    "cefuroxime": CARBAPENEMASE | ESBL | AMPC,
    "cefazolin": CARBAPENEMASE | ESBL | AMPC,
    "aztreonam": ESBL | AMPC | {"blakpc"},

    "ciprofloxacin": FLUOROQUINOLONE,
    "levofloxacin": FLUOROQUINOLONE,

    "gentamicin": {"aac(3)"} | AMINOGLYCOSIDE_16S,
    "tobramycin": {"aac(3)", "aac(6')", "ant(2)"} | AMINOGLYCOSIDE_16S,
    "amikacin": {"aac(6')"} | AMINOGLYCOSIDE_16S,

    "trimethoprim-sulfamethoxazole": {"sul", "dfr"},
    "tetracycline": {"tet"},
    "tigecycline": {"tet(x)", "TRUNC:ramr", "POINT:ramr"},
    "chloramphenicol": {"cat", "catа", "flor"},
    "colistin": COLISTIN,
    "polymyxin-b": COLISTIN,
    "fosfomycin": {"fosa"},
    "ampicillin": CARBAPENEMASE | ESBL | AMPC | {"blatem", "blashv", "blaoxa"},
    "ampicillin-sulbactam": CARBAPENEMASE | ESBL | AMPC,
    "piperacillin-tazobactam": CARBAPENEMASE | AMPC,
    "amoxicillin-clavulanate": CARBAPENEMASE | AMPC,
    "nitrofurantoin": {"TRUNC:nfsa", "TRUNC:nfsb", "POINT:nfsa", "POINT:nfsb"},
}
