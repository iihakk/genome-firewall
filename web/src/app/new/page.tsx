"use client";

import { useState } from "react";
import { PageHeader } from "@/components/Rail";
import { Alert, Button, Card, SectionLabel } from "@/components/ui";

const STEPS = [
  { k: "Assembling genome", d: "Reads stitched into contigs" },
  { k: "Calling determinants", d: "AMRFinderPlus: acquired genes, point mutations, truncations" },
  { k: "Normalising annotations", d: "Mapped onto the canonical resistance vocabulary" },
  { k: "Predicting susceptibility", d: "Per-antibiotic calibrated models" },
  { k: "Applying safety gates", d: "Confidence · novelty · completeness · coherence" },
];

export default function NewAnalysis() {
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(-1);

  function run() {
    setRunning(true);
    setStep(0);
    let i = 0;
    const tick = setInterval(() => {
      i += 1;
      setStep(i);
      if (i >= STEPS.length) {
        clearInterval(tick);
        setRunning(false);
      }
    }, 850);
  }

  return (
    <>
      <PageHeader
        title="New analysis"
        sub="Accession a specimen and submit its assembled genome. Analysis runs in minutes; the result enters the review queue rather than going straight to the ward."
      />

      <div className="grid grid-cols-[1fr_340px] gap-5">
        <Card>
          <SectionLabel>Specimen details</SectionLabel>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Accession" placeholder="KP-26-0874" />
            <Field label="Patient reference" placeholder="P7412" />
            <Field label="Specimen source" placeholder="Blood culture" />
            <Field label="Ward" placeholder="Intensive Care" />
            <Field label="Requesting clinician" placeholder="Dr. R. Okonkwo" />
            <Field label="Collected" placeholder="2026-07-19 04:10" />
          </div>

          <div className="mt-6">
            <SectionLabel>Assembled genome</SectionLabel>
            <div className="rounded-[10px] border border-dashed border-line-strong bg-surface-2/50 px-5 py-10 text-center">
              <p className="text-[13px] font-medium">Drop a FASTA file here</p>
              <p className="mt-1.5 text-[12px] text-muted">
                Or select a previously sequenced isolate from the run manifest
              </p>
              <Button variant="ghost" className="mt-4">
                Browse files
              </Button>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-line pt-5">
            <Button onClick={run} disabled={running}>
              {running ? "Analysing…" : "Run analysis"}
            </Button>
            <span className="text-[12px] text-faint">
              Typically completes in under three minutes
            </span>
          </div>

          {step >= 0 && (
            <ol className="mt-5 space-y-2.5 border-t border-line pt-5">
              {STEPS.map((s, i) => {
                const done = i < step;
                const active = i === step;
                return (
                  <li key={s.k} className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full text-[9px] font-bold ${
                        done
                          ? "bg-accent text-white"
                          : active
                            ? "bg-accent-soft text-accent ring-1 ring-accent"
                            : "bg-surface-2 text-faint"
                      }`}
                    >
                      {done ? "✓" : i + 1}
                    </span>
                    <div>
                      <div className={`text-[12.5px] ${done || active ? "font-medium" : "text-faint"}`}>
                        {s.k}
                      </div>
                      <div className="text-[11.5px] text-faint">{s.d}</div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>

        <div className="space-y-5">
          <Card>
            <SectionLabel>Scope</SectionLabel>
            <p className="text-[12.5px] leading-relaxed text-muted">
              This system is validated for <i>Klebsiella pneumoniae</i> only. Cross-species transfer was
              measured and the species-agnostic rule baseline outperformed it, so other organisms are not
              accepted.
            </p>
          </Card>
          <Alert tone="warn" title="Demonstration build">
            Submission is illustrative. The predictions shown throughout this application are precomputed
            from held-out isolates so the workflow can be demonstrated without a sequencing run attached.
          </Alert>
        </div>
      </div>
    </>
  );
}

function Field({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <div>
      <label className="mb-1.5 block text-[12px] font-medium text-muted">{label}</label>
      <input
        placeholder={placeholder}
        className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
      />
    </div>
  );
}
