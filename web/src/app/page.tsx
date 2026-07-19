"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Rail";
import { Button, Card, Chip, Dot, Stat, relTime } from "@/components/ui";
import { META, useSpecimens } from "@/lib/store";
import type { Specimen, SpecimenStatus } from "@/lib/types";

const FILTERS: { key: "all" | SpecimenStatus; label: string }[] = [
  { key: "all", label: "All" },
  { key: "review", label: "Awaiting review" },
  { key: "released", label: "Released" },
  { key: "reconciled", label: "Reconciled" },
];

const STATUS_LABEL: Record<
  SpecimenStatus,
  { text: string; glyph: string; tone: "accent" | "neutral" | "susceptible" }
> = {
  analysing: { text: "Analysing", glyph: "◌", tone: "neutral" },
  review: { text: "Review", glyph: "◔", tone: "accent" },
  released: { text: "Released", glyph: "✓", tone: "neutral" },
  reconciled: { text: "Reconciled", glyph: "✓", tone: "susceptible" },
};

/** Carbapenems are the last line. Resistance here is an infection-control event, not a data point. */
const LAST_LINE = ["meropenem", "ertapenem", "imipenem"];

/** Worklist flags answer one question: what does this specimen need from me next?
 *
 *  An earlier version flagged "genotype lookup would fail here", which is a claim about a
 *  competing method rather than a clinical instruction — useful when evaluating the system,
 *  useless when triaging a bench. That comparison now lives on Validation and Reconciliation,
 *  where a reader is actually assessing the tool.
 */
function triage(s: Specimen) {
  const flags: { label: string; tone: "resistant" | "deferred" | "accent"; glyph: string }[] = [];

  const carbR = s.drugs.filter((d) => LAST_LINE.includes(d.drug) && d.call === "RESISTANT").length;
  if (carbR > 0)
    flags.push({ label: "Carbapenem-resistant", tone: "resistant", glyph: "!" });

  const resistant = s.drugs.filter((d) => d.call === "RESISTANT").length;
  const called = s.drugs.filter((d) => d.call !== "INDETERMINATE").length;
  if (carbR === 0 && called > 0 && resistant / called >= 0.6)
    flags.push({ label: "Multi-drug resistant", tone: "resistant", glyph: "!" });

  const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE").length;
  if (deferred > 0)
    flags.push({ label: `${deferred} awaiting culture`, tone: "deferred", glyph: "?" });

  const novel = s.drugs.some((d) => d.reason?.includes("unrecognised"));
  if (novel) flags.push({ label: "Unrecognised machinery", tone: "accent", glyph: "◆" });

  return flags;
}

export default function Worklist() {
  const { rows, ready } = useSpecimens();
  const [filter, setFilter] = useState<"all" | SpecimenStatus>("all");

  const shown = useMemo(
    () => (filter === "all" ? rows : rows.filter((s) => s.status === filter)),
    [rows, filter],
  );

  const inReview = rows.filter((s) => s.status === "review").length;
  const critical = rows.filter((s) =>
    s.drugs.some((d) => LAST_LINE.includes(d.drug) && d.call === "RESISTANT"),
  ).length;

  return (
    <>
      <PageHeader
        title="Worklist"
        sub="Specimens sequenced and analysed. Nothing reaches the treating clinician until a qualified reviewer signs it out."
        actions={
          <>
            <Button variant="ghost">Import run</Button>
            <Link href="/new">
              <Button>New analysis</Button>
            </Link>
          </>
        }
      />

      <div className="stagger mb-6 grid grid-cols-4 gap-4">
        {[
          <Stat key="a" value={rows.length} label="specimens in the system" note={`${inReview} awaiting review`} />,
          <Stat
            key="b"
            value={critical}
            label="carbapenem-resistant isolates"
            note="infection control notified"
            tone="resistant"
          />,
          <Stat
            key="c"
            value={`${Math.round(META.deferral.mean_deferral * 100)}%`}
            label="of results deferred to culture"
            note="within expected range"
            tone="deferred"
          />,
          <Stat
            key="d"
            value={META.deferral.answered_accuracy.toFixed(3)}
            label="accuracy on answered cases"
            note={`+${META.deferral.accuracy_gain} vs forced answer`}
          />,
        ].map((el, i) => (
          <div key={i} style={{ animationDelay: `${i * 45}ms` }}>
            {el}
          </div>
        ))}
      </div>

      <Card pad={false} className="overflow-hidden">
        <div className="flex items-center gap-4 border-b border-line px-5 py-3.5">
          <h2 className="text-[14.5px] font-semibold">Active specimens</h2>
          <div className="ml-auto flex gap-1.5">
            {FILTERS.map((f) => {
              const on = filter === f.key;
              return (
                <button
                  key={f.key}
                  onClick={() => setFilter(f.key)}
                  aria-pressed={on}
                  className={`rounded-full px-3 py-1 text-[11.5px] font-medium ring-1 transition-all duration-200 ${
                    on
                      ? "bg-accent text-white ring-accent"
                      : "text-muted ring-line hover:text-ink hover:ring-line-strong"
                  }`}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-line">
              {["Accession", "Organism", "Source", "Ward", "Status", "Needs attention", "Received"].map(
                (h) => (
                  <th key={h} className="px-5 py-2.5 text-left text-[11.5px] font-semibold text-faint">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {shown.map((s, i) => (
              <Row key={s.id} s={s} index={i} animate={ready} />
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-[13px] text-faint">
                  No specimens in this state.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <p className="mt-4 max-w-[92ch] text-[11.5px] leading-relaxed text-faint">{META.note}</p>
    </>
  );
}

function Row({ s, index, animate }: { s: Specimen; index: number; animate: boolean }) {
  const router = useRouter();
  const st = STATUS_LABEL[s.status];
  const flags = triage(s);
  const href = `/specimen/${s.id}`;

  return (
    <tr
      onClick={() => router.push(href)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(href);
        }
      }}
      tabIndex={0}
      role="link"
      aria-label={`Open ${s.accession}`}
      className={`group cursor-pointer border-b border-line transition-colors duration-150 last:border-0 hover:bg-surface-2 focus-visible:bg-surface-2 ${
        animate ? "stagger-row" : ""
      }`}
      style={animate ? { animation: "rise 0.45s var(--ease-out) backwards", animationDelay: `${index * 35}ms` } : undefined}
    >
      <td className="px-5 py-3.5">
        <span className="flex items-center gap-2.5">
          <Dot urgent={s.priority === "urgent"} />
          <span className="font-mono text-[12.5px] font-medium group-hover:text-accent">
            {s.accession}
          </span>
        </span>
      </td>
      <td className="px-5 py-3.5 text-[13px] italic">{s.organism}</td>
      <td className="px-5 py-3.5 text-[13px] text-muted">{s.source}</td>
      <td className="px-5 py-3.5 text-[13px] text-muted">{s.ward}</td>
      <td className="px-5 py-3.5">
        <Chip tone={st.tone}>
          <span className="font-mono text-[10px]" aria-hidden>
            {st.glyph}
          </span>
          {st.text}
        </Chip>
      </td>
      <td className="px-5 py-3.5">
        <div className="flex flex-wrap gap-1.5">
          {flags.map((f) => (
            <Chip key={f.label} tone={f.tone}>
              <span className="font-mono text-[10px]" aria-hidden>
                {f.glyph}
              </span>
              {f.label}
            </Chip>
          ))}
          {flags.length === 0 && <span className="text-[12px] text-faint">—</span>}
        </div>
      </td>
      <td className="tnum px-5 py-3.5 font-mono text-[12px] text-muted">{relTime(s.receivedAt)}</td>
    </tr>
  );
}
