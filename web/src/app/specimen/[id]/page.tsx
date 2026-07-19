"use client";

import Link from "next/link";
import { use, useMemo, useState } from "react";
import { PageHeader } from "@/components/Rail";
import { ResultDialog } from "@/components/ResultDialog";
import { Button, CallChip, Card, Chip, Meter, SectionLabel, prettyToken } from "@/components/ui";
import { CURRENT_USER, useSpecimens } from "@/lib/store";
import { EXCLUDED_DRUGS, type Call, type DrugResult } from "@/lib/types";

/** Order by what a prescriber needs first.
 *
 *  Susceptible drugs are the actionable answer — the point of the report is finding the agent
 *  that still works — so they lead, most confident first. Deferred results follow, then resistant.
 *  Reading top to bottom is then: what to give, what we cannot say, what not to give.
 */
function clinicalOrder(drugs: DrugResult[]) {
  const rank: Record<Call, number> = { SUSCEPTIBLE: 0, INDETERMINATE: 1, RESISTANT: 2 };
  return [...drugs].sort((a, b) => {
    if (rank[a.call] !== rank[b.call]) return rank[a.call] - rank[b.call];
    if (a.call === "SUSCEPTIBLE") return a.probability - b.probability;
    if (a.call === "RESISTANT") return b.probability - a.probability;
    return a.drug.localeCompare(b.drug);
  });
}

export default function SpecimenPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { rows, ready, release, override } = useSpecimens();
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const s = rows.find((r) => r.id === id);
  const ordered = useMemo(() => (s ? clinicalOrder(s.drugs) : []), [s]);

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

  const options = s.drugs.filter((d) => d.call === "SUSCEPTIBLE");
  const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE");
  const lead = deferred.find((d) => d.lead);
  const drug = s.drugs.find((d) => d.drug === open) ?? null;

  return (
    <>
      <Link
        href="/"
        className="mb-4 inline-flex items-center gap-1.5 text-[12.5px] text-muted hover:text-accent"
      >
        <span aria-hidden>←</span> Worklist
      </Link>

      <PageHeader
        title={s.accession}
        sub={`${s.organism} · ${s.source} · ${s.ward}`}
        actions={
          s.status === "review" ? (
            <Button onClick={() => release(s.id, CURRENT_USER)}>Verify &amp; release</Button>
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

      <div className="mb-6 grid grid-cols-[1fr_310px] gap-5">
        <div className="space-y-4">
          {/* the answer, before the table */}
          <Card>
            <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
              <div className="min-w-0">
                <div className="text-[11.5px] font-semibold text-faint">Therapy options reported</div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {options.length > 0 ? (
                    options.map((d) => (
                      <button
                        key={d.drug}
                        onClick={() => setOpen(d.drug)}
                        className="rounded-full bg-susceptible-soft px-3 py-1 text-[12.5px] font-medium text-susceptible ring-1 ring-susceptible-line transition-transform duration-150 hover:scale-[1.03]"
                      >
                        {d.drug}
                      </button>
                    ))
                  ) : (
                    <span className="text-[13px] text-resistant">
                      No confidently susceptible agent — escalate to culture
                    </span>
                  )}
                </div>
              </div>
              <div className="ml-auto shrink-0 text-right text-[12px] text-muted">
                <div>
                  Culture reports in <b className="text-ink">48–72 h</b>
                </div>
                <div className="mt-0.5 font-medium text-accent">Available now</div>
              </div>
            </div>
          </Card>

          <Card>
            <SectionLabel>Full panel · {s.drugs.length} antibiotics</SectionLabel>
            <div className="grid grid-cols-[1fr_136px_120px_130px_50px] items-center gap-3 border-b border-line pb-2 text-[11px] font-semibold text-faint">
              <span>Antibiotic</span>
              <span>Call</span>
              <span>Confidence</span>
              <span>Driver</span>
              <span />
            </div>

            {ordered.map((d) => (
              <DrugRow
                key={d.drug}
                d={d}
                onOpen={() => setOpen(d.drug)}
                editing={editing === d.drug}
                onEdit={() => setEditing(editing === d.drug ? null : d.drug)}
                onOverride={(to, reason) => {
                  override(s.id, d.drug, to, reason, CURRENT_USER);
                  setEditing(null);
                }}
                canEdit={s.status === "review"}
              />
            ))}

            <div className="mt-4 border-t border-line pt-4 text-[12px]">
              {s.status === "review" ? (
                <span className="text-muted">
                  Reviewer · {CURRENT_USER} · <b className="text-deferred">not yet signed</b>
                  {deferred.length > 0 && ` · ${deferred.length} referred to culture`}
                </span>
              ) : (
                <span className="text-muted">
                  Released by {s.releasedBy} at {s.releasedAt?.replace("T", " ")}
                </span>
              )}
            </div>
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
                  <dt className="w-[88px] shrink-0 text-faint">{k}</dt>
                  <dd className="min-w-0 font-mono text-[12px] break-words">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          {lead?.lead && (
            <Card className="ring-1 ring-accent-line">
              <SectionLabel>Investigative lead</SectionLabel>
              <div className="mb-2 text-[11px] font-semibold tracking-wide text-accent uppercase">
                {lead.drug} · deferred
              </div>
              <p className="mb-3 text-[12.5px] leading-relaxed text-muted">
                {lead.lead.likelyMechanism}
              </p>
              <button
                onClick={() => setOpen(lead.drug)}
                className="text-[12px] font-medium text-accent hover:underline"
              >
                See recommended next step →
              </button>
            </Card>
          )}

          <Card>
            <SectionLabel>Determinants detected ({s.determinants.length})</SectionLabel>
            <div className="flex flex-wrap gap-1.5">
              {s.determinants.map((t) => (
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
              Highlighted markers are chromosomal mutations and truncations — mechanisms a
              gene-presence method cannot represent.
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

      {drug && <ResultDialog d={drug} onClose={() => setOpen(null)} />}
    </>
  );
}

function DrugRow({
  d,
  onOpen,
  editing,
  onEdit,
  onOverride,
  canEdit,
}: {
  d: DrugResult;
  onOpen: () => void;
  editing: boolean;
  onEdit: () => void;
  onOverride: (to: Call, reason: string) => void;
  canEdit: boolean;
}) {
  const [reason, setReason] = useState("");
  const [to, setTo] = useState<Call>("RESISTANT");
  const excluded = EXCLUDED_DRUGS[d.drug];
  // The driver must point the same way as the call. The largest contributor overall is often a
  // co-carried marker pushing the other direction, and labelling that "driver" misleads.
  const wantPositive = d.call === "RESISTANT";
  const driver = d.evidence
    .filter((e) => e.present && (wantPositive ? e.contribution > 0 : e.contribution < 0))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))[0];
  const driverInvisible = Boolean(driver?.invisibleToLookup);

  /* A single quiet marker, not a paragraph. The explanation lives one click away in the dialog,
     so the table stays readable at a glance. */
  const attention = d.lookupDangerouslyWrong
    ? {
        cls: "text-resistant bg-resistant-soft ring-resistant-line",
        glyph: "!",
        title: "Rule-based methods would report this susceptible — open for detail",
      }
    : d.call === "INDETERMINATE"
      ? {
          cls: "text-deferred bg-deferred-soft ring-deferred-line",
          glyph: "?",
          title: d.reason ?? "Deferred to culture",
        }
      : null;

  return (
    <div className="group/row border-b border-line last:border-0">
      <div className="grid grid-cols-[1fr_136px_120px_130px_50px] items-center gap-3 py-2.5">
        <button
          onClick={onOpen}
          className="flex items-center gap-1.5 text-left text-[13.5px] font-medium hover:text-accent"
        >
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
        <button
          onClick={onOpen}
          className="flex min-w-0 justify-start"
          title={driver ? driver.clinical : undefined}
        >
          {driver ? (
            <span
              className={`truncate rounded px-1.5 py-0.5 font-mono text-[11px] ${
                driverInvisible ? "bg-accent-soft text-accent ring-1 ring-accent-line" : "text-faint"
              }`}
            >
              {prettyToken(driver.token)}
            </span>
          ) : (
            <span className="font-mono text-[11px] text-faint">—</span>
          )}
        </button>
        <span className="flex items-center justify-end gap-1.5">
          {attention && (
            <button
              onClick={onOpen}
              title={attention.title}
              aria-label={attention.title}
              className={`grid size-[17px] place-items-center rounded-full text-[10px] font-bold ring-1 transition-transform duration-150 hover:scale-110 ${attention.cls}`}
            >
              {attention.glyph}
            </button>
          )}
          {canEdit && (
            <button
              onClick={onEdit}
              title="Override this call"
              aria-label={`Override ${d.drug}`}
              className="rounded p-0.5 text-faint opacity-0 transition-opacity duration-150 group-hover/row:opacity-100 hover:text-accent focus-visible:opacity-100"
            >
              <svg
                className="size-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
              </svg>
            </button>
          )}
        </span>
      </div>

      {editing && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[10px] bg-surface-2 p-3">
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
            placeholder="Reason (required, recorded in the audit trail)"
            className="min-w-[240px] flex-1 rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12.5px]"
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
  );
}
