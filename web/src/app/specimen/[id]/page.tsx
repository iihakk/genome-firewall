"use client";

import Link from "next/link";
import { use, useState } from "react";
import { PageHeader } from "@/components/Rail";
import { Alert, Button, CallChip, Card, Chip, Meter, SectionLabel, WarnIcon, prettyToken } from "@/components/ui";
import { CURRENT_USER, useSpecimens } from "@/lib/store";
import { EXCLUDED_DRUGS, type Call, type DrugResult, type Specimen } from "@/lib/types";

export default function SpecimenPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { rows, ready, release, override } = useSpecimens();
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const s = rows.find((r) => r.id === id);
  if (!ready) return <div className="py-20 text-center text-faint">Loading…</div>;
  if (!s)
    return (
      <div className="py-20 text-center">
        <p className="text-muted">Specimen not found.</p>
        <Link href="/" className="mt-3 inline-block text-accent">
          Back to worklist
        </Link>
      </div>
    );

  const danger = s.drugs.filter((d) => d.lookupDangerouslyWrong);
  const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE");
  const drug = s.drugs.find((d) => d.drug === open) ?? null;

  return (
    <>
      <Link href="/" className="mb-4 inline-flex items-center gap-1.5 text-[12.5px] text-muted hover:text-accent">
        <span aria-hidden>←</span> Worklist
      </Link>

      <PageHeader
        title={s.accession}
        sub={`${s.organism} · ${s.source} · ${s.ward}`}
        actions={
          s.status === "review" ? (
            <>
              <Button variant="ghost" onClick={() => setEditing(editing ? null : s.drugs[0].drug)}>
                Override a call
              </Button>
              <Button onClick={() => release(s.id, CURRENT_USER)}>Verify &amp; release</Button>
            </>
          ) : (
            <Chip tone="susceptible">
              <span className="font-mono text-[10px]" aria-hidden>
                ✓
              </span>
              Released by {s.releasedBy}
            </Chip>
          )
        }
      />

      <div className="mb-6 grid grid-cols-[1fr_320px] gap-5">
        <div className="space-y-4">
          <Card>
            <div className="mb-4 flex items-center gap-2.5 text-[12.5px] text-muted">
              <svg className="size-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
              <span>
                Culture-based susceptibility testing reports in{" "}
                <b className="text-ink">48–72 hours</b>. This result is available{" "}
                <b className="text-ink">now</b>.
              </span>
            </div>

            {danger.length > 0 && (
              <div className="mb-4">
                <Alert title="Genotype lookup would fail on this isolate">
                  For <b>{danger.map((d) => d.drug).join(", ")}</b>, a ResFinder-style lookup finds no known
                  determinant and would report <b>susceptible</b>. The laboratory result is resistant. The
                  responsible mechanism is present but is not an acquired gene, which is why gene-presence
                  tools cannot see it.
                </Alert>
              </div>
            )}

            <SectionLabel>Predicted susceptibility</SectionLabel>
            <div className="grid grid-cols-[1fr_128px_120px_92px_16px] items-center gap-3 border-b border-line pb-2 text-[11px] font-semibold text-faint">
              <span>Antibiotic</span>
              <span>Call</span>
              <span>Confidence</span>
              <span className="text-right">Lookup says</span>
              <span />
            </div>

            {s.drugs.map((d) => (
              <DrugRow
                key={d.drug}
                d={d}
                onOpen={() => setOpen(open === d.drug ? null : d.drug)}
                editing={editing === d.drug}
                onOverride={(to, reason) => {
                  override(s.id, d.drug, to, reason, CURRENT_USER);
                  setEditing(null);
                }}
                onEdit={() => setEditing(editing === d.drug ? null : d.drug)}
                canEdit={s.status === "review"}
              />
            ))}

            <SignOut s={s} />
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <SectionLabel>Specimen</SectionLabel>
            <dl className="space-y-2.5 text-[12.5px]">
              {[
                ["Patient", s.patientRef],
                ["Requested by", s.requestedBy],
                ["Collected", s.collectedAt.replace("T", " ")],
                ["Received", s.receivedAt.replace("T", " ")],
                ["Priority", s.priority === "urgent" ? "Urgent" : "Routine"],
                ["Genome", s.genomeId],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-3">
                  <dt className="w-[92px] shrink-0 text-faint">{k}</dt>
                  <dd className="min-w-0 font-mono text-[12px] break-words">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {deferred.length > 0 && deferred[0].lead && (
            <Card className="ring-1 ring-accent-line">
              <SectionLabel>Investigative lead</SectionLabel>
              <div className="mb-2 text-[11px] font-semibold tracking-wide text-accent uppercase">
                {deferred[0].drug} · deferred
              </div>
              <p className="mb-2 text-[12.5px] text-muted">{deferred[0].lead.likelyMechanism}</p>
              <p className="mb-3 text-[12.5px] text-muted">{deferred[0].lead.reasoning}</p>
              <p className="mb-3 text-[12.5px]">
                <b className="text-ink">Next step</b>{" "}
                <span className="text-muted">— {deferred[0].lead.recommendedAction}</span>
              </p>
              <div className="flex items-center gap-2.5">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="animate-grow h-full rounded-full bg-accent"
                    style={{ width: `${Math.round(deferred[0].lead.confidence * 100)}%` }}
                  />
                </div>
                <span className="tnum font-mono text-[12px] text-muted">
                  {deferred[0].lead.confidence.toFixed(2)}
                </span>
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                A hypothesis for the laboratory, not a prediction. The system declined to call this drug and
                that refusal stands.
              </p>
            </Card>
          )}

          <Card>
            <SectionLabel>Determinants detected ({s.determinants.length})</SectionLabel>
            <div className="flex flex-wrap gap-1.5">
              {s.determinants.map((t) => (
                <Chip
                  key={t}
                  mono
                  tone={t.startsWith("POINT:") || t.startsWith("TRUNC:") ? "resistant" : "neutral"}
                >
                  {prettyToken(t)}
                </Chip>
              ))}
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
              Red markers are target mutations and truncations — mechanisms no gene-presence lookup can
              represent.
            </p>
          </Card>

          <Card>
            <SectionLabel>Audit trail</SectionLabel>
            <ol className="space-y-3">
              {s.audit.map((a, i) => (
                <li key={i} className="relative pl-4 text-[12px]">
                  <span className="absolute top-1.5 left-0 size-1.5 rounded-full bg-line-strong" />
                  <div className="font-medium">{a.action}</div>
                  {a.detail && <div className="text-muted">{a.detail}</div>}
                  <div className="tnum mt-0.5 font-mono text-[11px] text-faint">
                    {a.at.replace("T", " ")} · {a.who}
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>

      {drug && <EvidenceDrawer d={drug} onClose={() => setOpen(null)} />}
    </>
  );
}

function DrugRow({
  d,
  onOpen,
  editing,
  onOverride,
  onEdit,
  canEdit,
}: {
  d: DrugResult;
  onOpen: () => void;
  editing: boolean;
  onOverride: (to: Call, reason: string) => void;
  onEdit: () => void;
  canEdit: boolean;
}) {
  const [reason, setReason] = useState("");
  const [to, setTo] = useState<Call>("RESISTANT");
  const excluded = EXCLUDED_DRUGS[d.drug];

  return (
    <div className="group/row border-b border-line last:border-0">
      <div className="grid grid-cols-[1fr_128px_120px_92px_16px] items-center gap-3 py-3">
        <button onClick={onOpen} className="flex items-center gap-2 text-left text-[13.5px] font-medium hover:text-accent">
          {d.drug}
          {excluded && (
            <span title={excluded} className="font-mono text-[10px] text-deferred">
              ⚠
            </span>
          )}
          {d.override && (
            <span title="Overridden by reviewer" className="font-mono text-[10px] text-accent">
              ✎
            </span>
          )}
        </button>
        <CallChip call={d.call} />
        <Meter value={d.probability} call={d.call} />
        <span
          className={`tnum text-right font-mono text-[11.5px] ${
            d.lookupDangerouslyWrong ? "font-bold text-resistant" : "text-faint"
          }`}
        >
          {d.lookupSays ? d.lookupSays.charAt(0) + d.lookupSays.slice(1).toLowerCase() : "—"}
        </span>
        <button onClick={onOpen} className="text-faint hover:text-accent" aria-label="Evidence">
          ›
        </button>
      </div>

      {d.lookupDangerouslyWrong && (
        <div className="flex items-start gap-2 pb-3 text-[11.5px] text-resistant">
          <WarnIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Lookup reports susceptible — no acquired determinant. Truth: resistant.
            {d.evidence.find((e) => e.invisibleToLookup && e.present) && (
              <>
                {" "}
                Driver:{" "}
                <span className="font-mono">
                  {prettyToken(d.evidence.find((e) => e.invisibleToLookup && e.present)!.token)}
                </span>
              </>
            )}
          </span>
        </div>
      )}
      {d.call === "INDETERMINATE" && d.reason && (
        <div className="flex items-start gap-2 pb-3 text-[11.5px] text-deferred">
          <WarnIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{d.reason}</span>
        </div>
      )}
      {d.override && (
        <div className="pb-3 text-[11.5px] text-accent">
          Overridden to {d.override.to.toLowerCase()} by {d.override.by} — {d.override.reason}
        </div>
      )}

      {canEdit && (
        <div className="pb-3">
          {!editing ? (
            <button
              onClick={onEdit}
              className="text-[11.5px] text-faint opacity-0 transition-opacity duration-150 group-hover/row:opacity-100 hover:text-accent focus-visible:opacity-100"
            >
              Override this call
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-2 rounded-[10px] bg-surface-2 p-3">
              <select
                value={to}
                onChange={(e) => setTo(e.target.value as Call)}
                className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12.5px]"
              >
                <option value="RESISTANT">Resistant</option>
                <option value="SUSCEPTIBLE">Susceptible</option>
                <option value="INDETERMINATE">Deferred</option>
              </select>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason (required)"
                className="min-w-[220px] flex-1 rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12.5px]"
              />
              <Button disabled={!reason.trim()} onClick={() => onOverride(to, reason.trim())}>
                Record override
              </Button>
              <Button variant="ghost" onClick={onEdit}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SignOut({ s }: { s: Specimen }) {
  const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE").length;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4 text-[12px]">
      {s.status === "review" ? (
        <span className="text-muted">
          Reviewer · {CURRENT_USER} · <b className="text-deferred">not yet signed</b>
          {deferred > 0 && ` · ${deferred} deferred to culture`}
        </span>
      ) : (
        <span className="text-muted">
          Released by {s.releasedBy} at {s.releasedAt?.replace("T", " ")}
        </span>
      )}
    </div>
  );
}

function EvidenceDrawer({ d, onClose }: { d: DrugResult; onClose: () => void }) {
  const max = Math.max(...d.evidence.map((e) => Math.abs(e.contribution)), 0.001);
  return (
    <>
      <div className="animate-fade fixed inset-0 z-40 bg-ink/35" onClick={onClose} />
      <aside className="animate-slide-in fixed inset-y-0 right-0 z-50 flex w-[420px] max-w-full flex-col border-l border-line bg-surface">
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="text-[11.5px] font-semibold text-faint">Evidence</div>
            <div className="mt-1 text-[16px] font-semibold">{d.drug}</div>
          </div>
          <button onClick={onClose} className="rounded-[8px] p-1.5 text-muted hover:bg-surface-2" aria-label="Close">
            <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="mb-4 flex items-center justify-between text-[12.5px]">
            <span className="text-muted">
              p(resistant) <b className="tnum font-mono text-ink">{d.probability.toFixed(2)}</b>
            </span>
            <span className="text-faint">isotonic-calibrated</span>
          </div>

          {d.evidence.map((e) => {
            const toward = e.contribution > 0 ? "resistant" : "susceptible";
            return (
              <div key={e.token} className="border-b border-line py-3.5 last:border-0">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="text-[13px] font-medium">
                    {e.gene}
                    <span
                      className={`ml-1.5 rounded px-1.5 py-px align-[1px] text-[10px] font-semibold tracking-wide uppercase ${
                        e.present ? "bg-resistant-soft text-resistant" : "bg-surface-2 text-faint"
                      }`}
                    >
                      {e.present ? "detected" : "not detected"}
                    </span>
                  </div>
                  <span className="tnum shrink-0 font-mono text-[12px] text-muted">
                    {e.contribution > 0 ? "+" : ""}
                    {e.contribution.toFixed(2)}
                  </span>
                </div>
                <div className="my-2 h-[3px] overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`h-full rounded-full ${e.contribution > 0 ? "bg-resistant" : "bg-susceptible"}`}
                    style={{ width: `${(Math.abs(e.contribution) / max) * 100}%` }}
                  />
                </div>
                <p className="text-[11.5px] text-faint">Pushes this call toward {toward}.</p>
                {e.present ? (
                  <>
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{e.clinical}</p>
                    {e.invisibleToLookup && (
                      <span className="mt-2 inline-block rounded bg-accent-soft px-2 py-0.5 text-[10.5px] font-medium text-accent">
                        invisible to gene-presence lookup
                      </span>
                    )}
                  </>
                ) : (
                  <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">
                    Not found in this genome. Its absence is part of why the model leans {toward}.
                  </p>
                )}
              </div>
            );
          })}

          {d.call === "INDETERMINATE" && d.reason && (
            <div className="mt-4 rounded-[10px] bg-deferred-soft p-3.5 ring-1 ring-deferred-line">
              <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-deferred uppercase">
                Why we are not answering
              </div>
              <p className="text-[12.5px] text-ink/80">
                {d.reason.charAt(0).toUpperCase() + d.reason.slice(1)}.
              </p>
              <p className="mt-2 text-[12.5px] text-ink/80">
                A confident wrong answer removes the caution that protects the patient. This case is referred
                to culture.
              </p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
