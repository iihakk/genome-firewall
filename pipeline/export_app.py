"""Export the web application's seed data.

The predictions, evidence, abstentions and lookup comparisons are all real — computed by the
pipeline from held-out isolates. What this adds is the laboratory envelope those results would
arrive in: accession numbers, specimen sources, wards, requesting clinicians, receipt times, and
the review/release state a real workflow moves through.

That envelope is synthetic and clearly labelled as such. The clinical content is not.

    python3 pipeline/export_app.py

Writes web/src/data/seed.json
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, HERE  # noqa: E402

APP_DATA = os.path.join(HERE, "web", "src", "data")

WARDS = ["Intensive Care", "Haematology", "General Medicine", "Renal", "Surgery",
         "Emergency", "Respiratory", "Transplant"]
CLINICIANS = ["Dr. R. Okonkwo", "Dr. M. Lindqvist", "Dr. S. Haddad", "Dr. P. Ramanathan",
              "Dr. J. Mwangi", "Dr. E. Nakamura", "Dr. T. Fernandes"]
REVIEWERS = ["Dr. A. Haidary", "Dr. L. Bergström"]
SOURCES = {
    "blood": ("Blood culture", "urgent"),
    "tracheal aspirate": ("Tracheal aspirate", "urgent"),
    "sputum": ("Sputum", "routine"),
    "urine": ("Urine", "routine"),
    "wound": ("Wound swab", "routine"),
    "tissue": ("Tissue", "routine"),
    "rectal swab": ("Rectal swab", "routine"),
}

# Deterministic pseudo-randomness: same input always produces the same demo, so screenshots and
# recordings stay reproducible across runs.
def rng(seed_text, n):
    h = hashlib.sha256(seed_text.encode()).digest()
    return h[n % len(h)]


def pick(seq, seed_text, n=0):
    return seq[rng(seed_text, n) % len(seq)]


def defer_reason_code(reason):
    if not reason:
        return None
    r = reason.lower()
    if "unrecognised" in r or "unfamiliar" in r:
        return "unrecognised machinery"
    if "sparse" in r or "incomplete" in r or "determinants detected" in r:
        return "sparse genome"
    if "contradicts" in r or "profile" in r:
        return "incoherent with profile"
    return "confidence"


def main():
    src = json.load(open(os.path.join(HERE, "web", "src", "data", "predictions.json")))
    isolates = src["isolates"]
    base = datetime(2026, 7, 19, 9, 0)

    specimens = []
    for i, iso in enumerate(isolates):
        gid = iso["genome_id"]
        meta = iso.get("meta") or {}
        raw_source = str(meta.get("source") or "").lower()
        label, prio = next(
            ((v[0], v[1]) for k, v in SOURCES.items() if k in raw_source),
            ("Sterile site", "routine"))

        # Newest first; roughly one specimen every few hours, as a real bench would see them.
        received = base - timedelta(hours=2 + i * 5, minutes=(rng(gid, 3) % 50))
        collected = received - timedelta(hours=6 + rng(gid, 4) % 18)

        n_defer = sum(1 for d in iso["drugs"] if d["call"] == "INDETERMINATE")
        n_danger = sum(1 for d in iso["drugs"] if d.get("rule_wrong_and_dangerous"))

        # First few still need a human; the rest have been signed out and some reconciled.
        if i < 3:
            status = "review"
        elif i < 9:
            status = "released"
        else:
            status = "reconciled"

        reviewer = pick(REVIEWERS, gid, 1)
        audit = [dict(at=received.isoformat(timespec="minutes"), who="System",
                      action="Specimen accessioned")]
        audit.append(dict(at=(received + timedelta(minutes=41)).isoformat(timespec="minutes"),
                          who="System", action="Sequencing complete · genome assembled"))
        audit.append(dict(at=(received + timedelta(minutes=44)).isoformat(timespec="minutes"),
                          who="Genome Firewall",
                          action=f"Analysis complete · {len(iso['drugs'])} antibiotics",
                          detail=f"{n_defer} deferred to culture"
                                 + (f" · {n_danger} lookup failure(s) flagged" if n_danger else "")))
        released_by = released_at = None
        if status in ("released", "reconciled"):
            rel = received + timedelta(hours=1, minutes=12)
            released_by, released_at = reviewer, rel.isoformat(timespec="minutes")
            audit.append(dict(at=released_at, who=reviewer, action="Verified and released",
                              detail="All calls reviewed; deferrals referred to culture"))
        if status == "reconciled":
            audit.append(dict(
                at=(received + timedelta(hours=54)).isoformat(timespec="minutes"),
                who="Laboratory", action="Culture AST received · reconciled"))

        drugs = []
        for d in iso["drugs"]:
            truth = d.get("truth")
            culture = truth if status == "reconciled" else None
            lookup = d.get("rule_says")
            drugs.append(dict(
                drug=d["drug"], call=d["call"], probability=d["probability"],
                reason=d.get("reason"),
                reasonCode=defer_reason_code(d.get("reason")),
                lookupSays=(lookup.upper() if lookup else None),
                lookupDangerouslyWrong=bool(d.get("rule_wrong_and_dangerous")),
                neighbourResistanceRate=d.get("neighbour_resistance_rate"),
                evidence=[dict(
                    token=e.get("token", ""), gene=e.get("gene", ""),
                    mechanism=e.get("mechanism"), clinical=e.get("clinical", ""),
                    contribution=e.get("contribution", 0), present=e.get("present", False),
                    invisibleToLookup=str(e.get("token", "")).startswith(("POINT:", "TRUNC:")),
                ) for e in d.get("evidence", [])],
                lead=(dict(
                    likelyMechanism=d["investigation"]["likely_mechanism"],
                    drugClassesAtRisk=d["investigation"]["drug_classes_at_risk"],
                    confidence=d["investigation"]["confidence"],
                    recommendedAction=d["investigation"]["recommended_action"],
                    reasoning=d["investigation"]["reasoning"],
                ) if d.get("investigation") else None),
                cultureResult=culture,
                override=None,
            ))

        specimens.append(dict(
            id=gid,
            accession=f"KP-26-{871 - i * 3:04d}",
            organism="Klebsiella pneumoniae",
            source=label,
            priority=prio,
            status=status,
            receivedAt=received.isoformat(timespec="minutes"),
            collectedAt=collected.isoformat(timespec="minutes"),
            requestedBy=pick(CLINICIANS, gid, 0),
            ward=pick(WARDS, gid, 2),
            patientRef=f"P{7100 + rng(gid, 5) % 800}",
            genomeId=gid,
            determinants=iso.get("determinants", []),
            drugs=drugs,
            audit=audit,
            releasedBy=released_by,
            releasedAt=released_at,
        ))

    payload = dict(
        specimens=specimens,
        validation=src["validation"],
        perDrug=src["per_drug"],
        discordance=src["discordance"],
        deferral=src["deferral"],
        provenance=src["provenance"],
        generatedAt=base.isoformat(timespec="minutes"),
        note=("Clinical content — predictions, evidence, abstentions and lookup comparisons — is "
              "computed from held-out isolates. Accessions, wards, requesting clinicians and "
              "timestamps are synthetic, to show the workflow a laboratory would use."),
    )
    os.makedirs(APP_DATA, exist_ok=True)
    dest = os.path.join(APP_DATA, "seed.json")
    json.dump(payload, open(dest, "w"), indent=1)

    from collections import Counter
    st = Counter(s["status"] for s in specimens)
    calls = Counter(d["call"] for s in specimens for d in s["drugs"])
    print(f"wrote {dest}")
    print(f"  {len(specimens)} specimens · {dict(st)}")
    print(f"  calls: {dict(calls)}")
    print(f"  lookup failures flagged: "
          f"{sum(1 for s in specimens for d in s['drugs'] if d['lookupDangerouslyWrong'])}")
    print(f"  investigative leads: "
          f"{sum(1 for s in specimens for d in s['drugs'] if d['lead'])}")


if __name__ == "__main__":
    main()
