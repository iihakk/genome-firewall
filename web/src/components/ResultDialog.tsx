"use client";

import { useEffect } from "react";
import { CallChip, Meter, prettyToken } from "@/components/ui";
import type { DrugResult } from "@/lib/types";

/** Centred result dialog.
 *
 *  Replaces a side drawer. A drawer competes with the table for attention and reads as a
 *  secondary panel; a result a clinician is about to act on deserves the middle of the screen.
 *  Content is ordered by what gets decided first: the call, then the evidence carrying it, then
 *  the caveat, then what to do next.
 */
export function ResultDialog({ d, onClose }: { d: DrugResult; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const present = d.evidence.filter((e) => e.present);
  const max = Math.max(...d.evidence.map((e) => Math.abs(e.contribution)), 0.001);
  const wantPositive = d.call === "RESISTANT";
  const driver = present
    .filter((e) => (wantPositive ? e.contribution > 0 : e.contribution < 0))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))[0];

  return (
    <div
      className="animate-fade fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-6 backdrop-blur-[2px]"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${d.drug} result`}
        onClick={(e) => e.stopPropagation()}
        className="card animate-dialog flex max-h-[86vh] w-full max-w-[600px] flex-col overflow-hidden p-0"
      >
        {/* header — the decision, stated once */}
        <div className="flex items-start gap-4 border-b border-line px-7 pt-6 pb-5">
          <div className="min-w-0 flex-1">
            <div className="text-[11.5px] font-semibold text-faint">Predicted susceptibility</div>
            <h2 className="mt-1 text-[21px] font-semibold tracking-[-0.02em]">{d.drug}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="-mt-1 rounded-lg p-2 text-faint transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-7 py-6">
          {/* the call */}
          <div className="mb-6 flex items-center gap-5">
            <CallChip call={d.call} />
            <div className="flex-1">
              <Meter value={d.probability} call={d.call} />
            </div>
            <div className="text-right">
              <div className="tnum font-mono text-[20px] leading-none font-semibold">
                {d.probability.toFixed(2)}
              </div>
              <div className="mt-1 text-[10.5px] text-faint">calibrated</div>
            </div>
          </div>

          {d.truth && (
            <div className="mb-6 flex items-center justify-between rounded-[10px] bg-surface-2 px-4 py-2.5 text-[12.5px]">
              <span className="text-muted">Culture result</span>
              <span className="font-medium">{d.truth}</span>
            </div>
          )}

          {/* why — evidence, densest information, kept scannable */}
          <div className="mb-2 text-[11.5px] font-semibold text-faint">
            What is driving this call
          </div>
          <div className="space-y-4">
            {d.evidence.map((e) => (
              <div key={e.token}>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[13px] font-medium">
                    {e.mechanism ? e.gene : prettyToken(e.token)}
                    {!e.present && (
                      <span className="ml-2 text-[11px] font-normal text-faint">not detected</span>
                    )}
                  </span>
                  <span className="tnum shrink-0 font-mono text-[11.5px] text-muted">
                    {e.contribution > 0 ? "+" : ""}
                    {e.contribution.toFixed(2)}
                  </span>
                </div>
                <div className="mt-1.5 h-[3px] overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`h-full rounded-full ${e.contribution > 0 ? "bg-resistant" : "bg-susceptible"}`}
                    style={{ width: `${(Math.abs(e.contribution) / max) * 100}%` }}
                  />
                </div>
                {e.present && e.clinical && (
                  <p className="mt-2 text-[12px] leading-relaxed text-muted">{e.clinical}</p>
                )}
                {e.present && e.invisibleToLookup && (
                  <span className="mt-2 inline-block rounded bg-accent-soft px-2 py-0.5 text-[10.5px] font-medium text-accent ring-1 ring-accent-line">
                    chromosomal — invisible to gene-presence methods
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* caveat, only when there is one */}
          {d.lookupDangerouslyWrong && (
            <div className="mt-6 rounded-[10px] bg-resistant-soft p-4 ring-1 ring-resistant-line">
              <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-resistant uppercase">
                Rule-based methods would miss this
              </div>
              <p className="text-[12.5px] leading-relaxed text-ink/75">
                {driver?.invisibleToLookup ? (
                  <>
                    The mechanism carrying this call is chromosomal (
                    <span className="font-mono">{prettyToken(driver.token)}</span>). Screening only
                    for acquired resistance genes returns nothing, so such a method reports this
                    isolate as susceptible.
                  </>
                ) : (
                  <>
                    No determinant in the reference rule set matches this isolate, so a rule-based
                    method reports it susceptible. This call rests on the wider resistance profile
                    rather than a single named gene — weaker evidence, and worth confirming.
                  </>
                )}
              </p>
            </div>
          )}

          {d.call === "INDETERMINATE" && d.reason && (
            <div className="mt-6 rounded-[10px] bg-deferred-soft p-4 ring-1 ring-deferred-line">
              <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-deferred uppercase">
                Why we are not answering
              </div>
              <p className="text-[12.5px] leading-relaxed text-ink/75">
                {d.reason.charAt(0).toUpperCase() + d.reason.slice(1)}. A confident wrong answer
                removes the caution that protects the patient, so this drug is referred to culture.
              </p>
            </div>
          )}

          {d.lead && (
            <div className="mt-6 rounded-[10px] bg-accent-soft p-4 ring-1 ring-accent-line">
              <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-accent uppercase">
                Investigative lead
              </div>
              <p className="text-[12.5px] leading-relaxed text-ink/75">{d.lead.likelyMechanism}</p>
              <p className="mt-2.5 text-[12.5px] leading-relaxed">
                <b>Next step</b>{" "}
                <span className="text-ink/75">— {d.lead.recommendedAction}</span>
              </p>
              <div className="mt-3 flex items-center gap-3">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/60">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${d.lead.confidence * 100}%` }}
                  />
                </div>
                <span className="tnum font-mono text-[11.5px] text-muted">
                  {d.lead.confidence.toFixed(2)}
                </span>
              </div>
              <p className="mt-2.5 text-[11px] leading-relaxed text-faint">
                A hypothesis for the laboratory, not a prediction. The refusal above stands.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-line bg-surface-2/50 px-7 py-4 text-[11.5px] text-faint">
          <span>Press Esc to close</span>
          {d.override && (
            <span className="text-accent">
              Overridden by {d.override.by} — {d.override.reason}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
