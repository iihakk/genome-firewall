"use client";

import { useRef, useState } from "react";
import { PageHeader } from "@/components/Rail";
import { Alert, Button, CallChip, Card, Chip, Meter, SectionLabel, prettyToken, shortDrug } from "@/components/ui";
import type { Call } from "@/lib/types";

/** Live analysis.
 *
 *  Every result on this page comes from the model running now, not from a stored answer. The
 *  uploaded profile is posted to /api/analyze, which invokes the same cached models the
 *  validation report describes and applies the same four abstention gates.
 */

interface AnalysisResult {
  accession: string;
  organism: string;
  source?: string | null;
  determinantsSubmitted: number;
  determinantsRecognised: string[];
  determinantsUnrecognised: string[];
  /** Normalised cleanly but never seen in training — this is what trips the novelty gate. */
  determinantsNovel: string[];
  elapsedMs?: number;
  results: {
    drug: string;
    call: Call;
    probability: number;
    reason: string | null;
    unknownMachinery: string[];
  }[];
}

const SAMPLES = [
  {
    file: "treatable-isolate.json",
    label: "Lightly armed isolate",
    note: "Therapy cleared rather than refused",
  },
  {
    file: "carbapenemase-mutations.json",
    label: "Carbapenemase + target mutations",
    note: "The multidrug case",
  },
  {
    file: "mutations-no-carbapenemase.json",
    label: "Chromosomal mutations only",
    note: "Where gene lookup reports susceptible",
  },
  {
    file: "unfamiliar-machinery.json",
    label: "Unfamiliar machinery",
    note: "Trips the novelty gate",
  },
  {
    file: "rich-profile.json",
    label: "Heavily armed isolate",
    note: "Most agents expected to fail",
  },
];

const STEPS = [
  "Reading determinant profile",
  "Normalising annotations onto the resistance vocabulary",
  "Scoring each antibiotic",
  "Applying safety gates",
];

export default function NewAnalysis() {
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(-1);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function analyse(profile: unknown) {
    setBusy(true);
    setError(null);
    setResult(null);
    setStep(0);
    // The stepper paces itself off the request; inference is fast enough that the stages would
    // otherwise flash past unread. The elapsed time reported afterwards is the real one.
    const ticker = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 380);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Analysis failed.");
      setStep(STEPS.length);
      setResult(data as AnalysisResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
      setStep(-1);
    } finally {
      clearInterval(ticker);
      setBusy(false);
    }
  }

  async function runSample(file: string) {
    try {
      const profile = await fetch(`/demo-files/${file}`).then((r) => r.json());
      await analyse(profile);
    } catch {
      setError(`Could not load ${file}.`);
    }
  }

  async function onFile(f: File) {
    try {
      await analyse(JSON.parse(await f.text()));
    } catch {
      setError("Could not read that file. Expected JSON containing a `determinants` array.");
    }
  }

  return (
    <>
      <PageHeader
        title="New analysis"
        sub="Submit an isolate's determinant profile. Prediction runs against the live model and the result enters the review queue rather than going straight to the ward."
      />

      <div className="grid grid-cols-[1fr_320px] items-start gap-5">
        <div className="space-y-4">
          <Card>
            <SectionLabel>Submit a profile</SectionLabel>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const f = e.dataTransfer.files?.[0];
                if (f) onFile(f);
              }}
              className={`rounded-[10px] border border-dashed px-5 py-9 text-center transition-colors ${
                dragging ? "border-accent bg-accent-soft/40" : "border-line-strong bg-surface-2/40"
              }`}
            >
              <p className="text-[13px] font-medium">Drop an AMRFinderPlus profile here</p>
              <p className="mx-auto mt-1.5 max-w-[54ch] text-[12px] leading-relaxed text-muted">
                JSON listing the determinants called for the isolate — what a laboratory already
                holds once the genome is assembled and annotated.
              </p>
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onFile(f);
                  e.target.value = "";
                }}
              />
              <Button variant="ghost" className="mt-4" disabled={busy} onClick={() => fileRef.current?.click()}>
                Choose file
              </Button>
            </div>

            <div className="mt-5 border-t border-line pt-4">
              <div className="mb-2.5 text-[11.5px] font-semibold text-faint">
                Or analyse one of these unseen isolates
              </div>
              <div className="grid grid-cols-2 gap-2">
                {SAMPLES.map((s) => (
                  <button
                    key={s.file}
                    disabled={busy}
                    onClick={() => runSample(s.file)}
                    className="rounded-[10px] border border-line px-3 py-2.5 text-left transition-colors hover:border-accent disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <div className="text-[12.5px] font-medium">{s.label}</div>
                    <div className="mt-0.5 text-[11.5px] text-faint">{s.note}</div>
                  </button>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                Each is a real isolate quarantined from training and absent from the caseload this
                application ships with, so the model has genuinely not seen it. The same files are
                downloadable from <code className="font-mono">demo-files/</code> in the repository.
              </p>
            </div>
          </Card>

          {step >= 0 && (
            <Card>
              <SectionLabel>Analysis</SectionLabel>
              <ol className="space-y-2.5">
                {STEPS.map((label, i) => {
                  const done = i < step;
                  const active = i === step && busy;
                  return (
                    <li key={label} className="flex items-center gap-3">
                      <span
                        className={`grid size-[18px] shrink-0 place-items-center rounded-full text-[9px] font-bold transition-colors ${
                          done
                            ? "bg-accent text-white"
                            : active
                              ? "bg-accent-soft text-accent ring-1 ring-accent"
                              : "bg-surface-2 text-faint"
                        }`}
                      >
                        {done ? "✓" : i + 1}
                      </span>
                      <span className={`text-[12.5px] ${done || active ? "" : "text-faint"}`}>
                        {label}
                      </span>
                      {active && <span className="ml-auto text-[11px] text-faint">working…</span>}
                    </li>
                  );
                })}
              </ol>
              {result && (
                <p className="tnum mt-3.5 border-t border-line pt-3.5 text-[11.5px] text-faint">
                  Completed in {((result.elapsedMs ?? 0) / 1000).toFixed(1)}s ·{" "}
                  {result.determinantsSubmitted} determinants submitted,{" "}
                  {result.determinantsRecognised.length} recognised
                  {result.determinantsUnrecognised.length > 0 &&
                    `, ${result.determinantsUnrecognised.length} unrecognised`}
                </p>
              )}
            </Card>
          )}

          {error && <Alert title="Analysis failed">{error}</Alert>}

          {result && <ResultCard r={result} />}
        </div>

        <div className="space-y-4">
          <Card>
            <SectionLabel>Scope</SectionLabel>
            <p className="text-[12.5px] leading-relaxed text-muted">
              Calls are issued for <i>Klebsiella pneumoniae</i>. A model trained on one species must
              not be pointed at another — we measured that, and the species-agnostic rule baseline
              won. The method itself retrains per organism and holds: the same pipeline reaches
              0.946 mean AUC on <i>Staphylococcus aureus</i>, a Gram-positive whose resistance
              biology shares nothing with Klebsiella.
            </p>
          </Card>

          {result && result.determinantsNovel?.length > 0 && (
            <Card>
              <SectionLabel>Unfamiliar machinery ({result.determinantsNovel.length})</SectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {result.determinantsNovel.slice(0, 14).map((t) => (
                  <Chip key={t} mono tone="deferred">
                    {prettyToken(t)}
                  </Chip>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                Recognised as resistance machinery but absent from training, so the model has no
                basis for scoring it. Their presence blocks any susceptible call — the probability
                was computed without this evidence.
              </p>
            </Card>
          )}

          {result && result.determinantsUnrecognised.length > 0 && (
            <Card>
              <SectionLabel>
                Could not be normalised ({result.determinantsUnrecognised.length})
              </SectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {result.determinantsUnrecognised.slice(0, 14).map((t) => (
                  <Chip key={t} mono tone="neutral">
                    {t}
                  </Chip>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                Annotations the vocabulary could not map onto a known determinant — mistranslations
                and partial hits, which carry no usable signal either way.
              </p>
            </Card>
          )}

          {result && (
            <Card>
              <SectionLabel>Recognised ({result.determinantsRecognised.length})</SectionLabel>
              <div className="flex flex-wrap gap-1.5">
                {result.determinantsRecognised.map((t) => (
                  <Chip
                    key={t}
                    mono
                    tone={t.startsWith("POINT:") || t.startsWith("TRUNC:") ? "accent" : "neutral"}
                  >
                    {prettyToken(t)}
                  </Chip>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                Highlighted tokens are chromosomal mutations and gene losses — invisible to
                gene-presence lookup, and the reason this model beats one.
              </p>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function ResultCard({ r }: { r: AnalysisResult }) {
  const options = r.results.filter((x) => x.call === "SUSCEPTIBLE");
  const deferred = r.results.filter((x) => x.call === "INDETERMINATE");

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line pb-4">
        <h2 className="text-[16px] font-semibold">{r.accession}</h2>
        <span className="text-[12.5px] text-muted italic">{r.organism}</span>
        {r.source && <span className="text-[12.5px] text-muted">· {r.source}</span>}
      </div>

      <div className="mb-5 rounded-[10px] bg-surface-2 px-4 py-3">
        <div className="text-[11.5px] font-semibold text-faint">Therapy options reported</div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {options.length > 0 ? (
            options.map((x) => (
              <span
                key={x.drug}
                className="rounded-full bg-susceptible-soft px-3 py-1 text-[12.5px] font-medium text-susceptible ring-1 ring-susceptible-line"
              >
                {shortDrug(x.drug)}
              </span>
            ))
          ) : (
            <span className="text-[13px] font-medium text-resistant">
              None — no agent clears the safety gates. Escalate to culture.
            </span>
          )}
        </div>
        {deferred.length > 0 && (
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-faint">
            {deferred.length} further {deferred.length === 1 ? "agent is" : "agents are"} deferred to
            culture rather than guessed.
          </p>
        )}
      </div>

      <div className="grid grid-cols-[152px_130px_1fr_46px] items-center gap-3 border-b border-line pb-2 text-[11px] font-semibold text-faint">
        <span>Antibiotic</span>
        <span>Call</span>
        <span>Confidence</span>
        <span className="text-right">p</span>
      </div>
      {r.results.map((x) => (
        <div key={x.drug} className="border-b border-line last:border-0">
          <div className="grid grid-cols-[152px_130px_1fr_46px] items-center gap-3 py-2.5">
            <span title={x.drug} className="truncate text-[13.5px] font-medium">
              {shortDrug(x.drug)}
            </span>
            <CallChip call={x.call} size="sm" />
            <Meter value={x.probability} call={x.call} />
            <span className="tnum text-right font-mono text-[12px] text-muted">
              {x.probability.toFixed(2)}
            </span>
          </div>
          {x.reason && (
            <div className="pb-2.5 pl-[152px] text-[11.5px] leading-relaxed text-deferred">
              Deferred — {x.reason}.
            </div>
          )}
        </div>
      ))}

      <p className="mt-4 border-t border-line pt-4 text-[12px] leading-relaxed text-muted">
        Result queued for review. Nothing reaches the treating clinician until a qualified reviewer
        signs it out.
      </p>
    </Card>
  );
}
