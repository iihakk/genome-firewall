"""Clinical annotations for resistance genes.

Starter content written from standard medical microbiology. The clinician on the team should
review and override these — `clinician_gene_worksheet.csv` is the intake form. Each entry is what
gets shown in the evidence drawer, so it must be readable by a doctor at 3 a.m., not a
bioinformatician.

`driver` marks whether the gene is a genuine causal mechanism for the drug it's attached to, or a
passenger that merely travels on the same plasmid. That distinction is what stops the evidence
panel from implying causation it hasn't earned.
"""

ANNOTATIONS = {
    "KPC family": dict(
        short="KPC carbapenemase",
        mechanism="Enzymatic degradation",
        defeats="Carbapenems (meropenem, imipenem, ertapenem), penicillins, cephalosporins",
        clinical="Class A carbapenemase. Hydrolyses the last-resort carbapenems. Plasmid-borne "
                 "and strongly associated with the ST258 global outbreak clone.",
        driver=True,
    ),
    "OXA-48 family": dict(
        short="OXA-48 carbapenemase",
        mechanism="Enzymatic degradation",
        defeats="Carbapenems (weakly), penicillins",
        clinical="Class D carbapenemase. Hydrolyses carbapenems weakly, so it is easy to miss on "
                 "routine testing, and often co-carried with an ESBL that widens the gap.",
        driver=True,
    ),
    "NDM": dict(
        short="NDM metallo-beta-lactamase",
        mechanism="Enzymatic degradation",
        defeats="All beta-lactams except aztreonam",
        clinical="Class B metallo-enzyme requiring zinc. Not inhibited by standard beta-lactamase "
                 "inhibitors, which removes most of the usual rescue options.",
        driver=True,
    ),
    "CTX-M family": dict(
        short="CTX-M extended-spectrum beta-lactamase",
        mechanism="Enzymatic degradation",
        defeats="Third-generation cephalosporins (ceftriaxone, cefotaxime, ceftazidime)",
        clinical="The dominant ESBL worldwide. Defeats cephalosporins but NOT carbapenems — "
                 "which is exactly why carbapenems became the fallback drug.",
        driver=True,
    ),
    "TEM family": dict(
        short="TEM beta-lactamase",
        mechanism="Enzymatic degradation",
        defeats="Penicillins; extended-spectrum variants also cephalosporins",
        clinical="Broad-spectrum penicillinase. Common and usually not carbapenem-relevant.",
        driver=True,
    ),
    "SHV family": dict(
        short="SHV beta-lactamase",
        mechanism="Enzymatic degradation",
        defeats="Penicillins; some variants extend to cephalosporins",
        clinical="Near-universal in Klebsiella pneumoniae, frequently chromosomal, so its presence "
                 "alone says little about the isolate.",
        driver=True,
    ),
    "Aminoglycoside N(3)-acetyltransferase": dict(
        short="AAC(3) aminoglycoside acetyltransferase",
        mechanism="Drug modification",
        defeats="Gentamicin, tobramycin",
        clinical="Chemically inactivates gentamicin. A genuine portable mechanism that travels on "
                 "plasmids across unrelated lineages.",
        driver=True,
    ),
    "Aminoglycoside N(6')-acetyltransferase": dict(
        short="AAC(6') aminoglycoside acetyltransferase",
        mechanism="Drug modification",
        defeats="Tobramycin, amikacin, kanamycin",
        clinical="Substrate range varies by variant. The AAC(6')-Ib-cr variant additionally "
                 "modifies fluoroquinolones, giving one gene two drug classes.",
        driver=True,
    ),
    "Aminoglycoside 3'-phosphotransferase": dict(
        short="APH(3') aminoglycoside phosphotransferase",
        mechanism="Drug modification",
        defeats="Kanamycin, neomycin",
        clinical="Does NOT modify gentamicin or amikacin. Its presence is a poor guide to those "
                 "drugs and is a common source of over-calling resistance.",
        driver=False,
    ),
    "Aminoglycoside 6-phosphotransferase": dict(
        short="APH(6) aminoglycoside phosphotransferase",
        mechanism="Drug modification",
        defeats="Streptomycin",
        clinical="Streptomycin-specific. Rarely relevant to current therapy; usually a passenger.",
        driver=False,
    ),
    "Aminoglycoside 3''-nucleotidyltransferase": dict(
        short="ANT(3'') nucleotidyltransferase",
        mechanism="Drug modification",
        defeats="Streptomycin, spectinomycin",
        clinical="Classic integron cargo. Signals a mobile resistance platform more than it "
                 "predicts any drug currently in use.",
        driver=False,
    ),
    "QnrB": dict(
        short="QnrB quinolone-protection protein",
        mechanism="Target protection",
        defeats="Fluoroquinolones (ciprofloxacin, levofloxacin) — partially",
        clinical="Shields DNA gyrase from the drug. Confers only low-level resistance alone, but "
                 "lowers the bar for full resistance to emerge during treatment.",
        driver=True,
    ),
    "Dihydropteroate synthase": dict(
        short="Sul dihydropteroate synthase",
        mechanism="Target replacement",
        defeats="Sulfonamides (component of trimethoprim/sulfamethoxazole)",
        clinical="An alternative version of the enzyme the drug is designed to block, so the "
                 "pathway keeps running with the drug bound elsewhere.",
        driver=True,
    ),
    "Chloramphenicol O-acetyltransferase": dict(
        short="Cat chloramphenicol acetyltransferase",
        mechanism="Drug modification",
        defeats="Chloramphenicol",
        clinical="Chloramphenicol is rarely used in this setting; typically a passenger gene.",
        driver=False,
    ),
    "Tetracycline resistance": dict(
        short="Tet efflux pump",
        mechanism="Efflux",
        defeats="Tetracyclines",
        clinical="Pumps the drug out. Note presence does not guarantee resistance — the gene can "
                 "be present but not expressed.",
        driver=True,
    ),
    "Macrolide 2'-phosphotransferase": dict(
        short="Mph(A) macrolide phosphotransferase",
        mechanism="Drug modification",
        defeats="Macrolides (azithromycin, erythromycin)",
        clinical="Limited relevance for Gram-negative bloodstream infection; usually a passenger.",
        driver=False,
    ),
    "QacE": dict(
        short="QacEΔ1 efflux",
        mechanism="Efflux",
        defeats="Quaternary ammonium disinfectants",
        clinical="A disinfectant-resistance marker, not an antibiotic mechanism. Its real value is "
                 "as a flag for a class 1 integron carrying other resistance cargo.",
        driver=False,
    ),
}


def annotate(product: str):
    """Match a BV-BRC product string to a clinical annotation, longest key first."""
    for key in sorted(ANNOTATIONS, key=len, reverse=True):
        if key.lower() in product.lower():
            return ANNOTATIONS[key]
    return None
