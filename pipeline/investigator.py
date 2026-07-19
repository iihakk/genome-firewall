"""The investigator agent — what happens after the firewall refuses.

Abstention is the system's safety mechanism, but on its own it is a dead end: it tells the
clinician to wait 48-72 hours, which is the problem we set out to solve. We defer on 19% of
isolates and, until now, did nothing with them.

This agent picks up those cases. Given the determinants the model could not interpret, it
produces a structured investigative lead: what the unrecognised protein most likely is, which
drug classes it plausibly affects, how confident that reading is, and what the laboratory should
check first.

This is deliberately NOT a prediction. It is surfaced to the clinician as a hypothesis with its
uncertainty attached, because the whole point of the refusal was that we do not know. An agent
that quietly converted refusals back into confident answers would defeat the mechanism it is
attached to.

    python3 pipeline/investigator.py [--limit N]

Writes data/investigations.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from features import DATA, HERE, load_ncbi  # noqa: E402

MODEL = "gpt-4o-mini"

SYSTEM = """You are a clinical microbiologist advising on a bacterial isolate where an automated \
susceptibility predictor has declined to give an answer.

You will be told which resistance determinants were detected, which the predictor could not \
interpret, and why it refused. Produce an investigative lead for the laboratory.

Requirements:
- You are NOT predicting susceptibility. The predictor refused for a reason. Your job is to say \
what should be investigated, not to overturn the refusal.
- `likely_mechanism`: your best reading of what the uninterpreted determinants do, in plain \
clinical language.
- `drug_classes_at_risk`: classes plausibly affected, lowercase.
- `confidence`: 0-1 in your mechanistic reading. Be conservative; these are cases the model \
already found ambiguous.
- `recommended_action`: the single most useful next step for the lab or the clinician, concrete \
and specific.
- `reasoning`: two sentences maximum, aimed at a clinician, not a bioinformatician.
- If the determinants genuinely do not support any confident reading, say so plainly and set \
confidence low. That is a useful answer."""

SCHEMA = {
    "type": "object",
    "properties": {
        "likely_mechanism": {"type": "string"},
        "drug_classes_at_risk": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "recommended_action": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["likely_mechanism", "drug_classes_at_risk", "confidence",
                 "recommended_action", "reasoning"],
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
        sys.exit("no OPENAI_API_KEY")
    return OpenAI(api_key=key)


def investigate(cl, drug, reason, known, unknown):
    msg = (f"Antibiotic under consideration: {drug}\n"
           f"The predictor refused because: {reason}\n\n"
           f"Determinants it recognised: {', '.join(sorted(known)) or 'none'}\n"
           f"Determinants it could NOT interpret: {', '.join(sorted(unknown)) or 'none'}\n\n"
           "Give the laboratory an investigative lead.")
    r = cl.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "lead", "strict": True, "schema": SCHEMA}})
    return json.loads(r.choices[0].message.content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    PRED = os.path.join(HERE, "web", "src", "data", "predictions.json")
    payload = json.load(open(PRED))
    feats, _, _ = load_ncbi("klebsiella")
    split = json.load(open(os.path.join(DATA, "split_v2.json")))
    known_vocab = {t for g in split["train"] for t in feats.get(g, ())}

    # Every abstention in the demo set, deduplicated by (reason, unknown determinants) so we pay
    # once per distinct situation rather than once per isolate.
    seen, jobs = set(), []
    for iso in payload["isolates"]:
        toks = set(iso["determinants"])
        unknown = sorted(toks - known_vocab)
        for d in iso["drugs"]:
            if d["call"] != "INDETERMINATE":
                continue
            key = (d["drug"], d["reason"], tuple(unknown))
            if key in seen:
                continue
            seen.add(key)
            jobs.append(dict(isolate=iso["genome_id"], drug=d["drug"], reason=d["reason"],
                             probability=d["probability"],
                             known=sorted(toks & known_vocab)[:14], unknown=unknown))
    jobs = jobs[:args.limit]
    print(f"{len(jobs)} distinct abstentions to investigate")

    cl = client()
    out = []
    for i, j in enumerate(jobs, 1):
        try:
            lead = investigate(cl, j["drug"], j["reason"], j["known"], j["unknown"])
        except Exception as e:
            print(f"  {i}/{len(jobs)} failed: {repr(e)[:80]}")
            continue
        out.append({**j, "lead": lead})
        print(f"  {i}/{len(jobs)}  {j['drug']:<28} conf={lead['confidence']:.2f}  "
              f"{lead['likely_mechanism'][:52]}", flush=True)
        json.dump(out, open(os.path.join(DATA, "investigations.json"), "w"), indent=1)

    # Fold the leads back into the UI payload so the drawer can show them.
    by_key = {(o["isolate"], o["drug"]): o["lead"] for o in out}
    for iso in payload["isolates"]:
        for d in iso["drugs"]:
            lead = by_key.get((iso["genome_id"], d["drug"]))
            if lead:
                d["investigation"] = lead
    json.dump(payload, open(PRED, "w"), indent=1)

    if out:
        conf = sum(o["lead"]["confidence"] for o in out) / len(out)
        print(f"\n{len(out)} leads generated · mean confidence {conf:.2f}")
        print(f"wrote {os.path.join(DATA, 'investigations.json')} and refreshed the UI payload")


if __name__ == "__main__":
    main()
