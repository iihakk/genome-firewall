"use client";

import Link from "next/link";
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

export default function Worklist() {
  const { rows, ready } = useSpecimens();
  const [filter, setFilter] = useState<"all" | SpecimenStatus>("all");

  const shown = useMemo(
    () => (filter === "all" ? rows : rows.filter((s) => s.status === filter)),
    [rows, filter],
  );

  const inReview = rows.filter((s) => s.status === "review").length;
  const flagged = rows.filter((s) => s.drugs.some((d) => d.lookupDangerouslyWrong)).length;

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
        <Stat value={rows.length} label="specimens in the system" note={`${inReview} awaiting review`} />
        <Stat
          value={`${Math.round(META.deferral.mean_deferral * 100)}%`}
          label="deferred to culture"
          note="within expected range"
          tone="deferred"
        />
        <Stat
          value={META.deferral.answered_accuracy.toFixed(3)}
          label="accuracy on answered cases"
          note={`+${META.deferral.accuracy_gain} vs forced answer`}
        />
        <Stat
          value={flagged}
          label="specimens where genotype lookup would fail"
          note="each reviewed individually"
          tone="resistant"
        />
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
              {["Accession", "Organism", "Source", "Ward", "Status", "Flags", "Received"].map((h) => (
                <th key={h} className="px-5 py-2.5 text-left text-[11.5px] font-semibold text-faint">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={ready ? "stagger" : ""}>
            {shown.map((s) => (
              <Row key={s.id} s={s} />
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

function Row({ s }: { s: Specimen }) {
  const st = STATUS_LABEL[s.status];
  const danger = s.drugs.filter((d) => d.lookupDangerouslyWrong).length;
  const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE").length;

  return (
    <tr className="group border-b border-line transition-colors duration-150 last:border-0 hover:bg-surface-2">
      <td className="px-5 py-3.5">
        <Link href={`/specimen/${s.id}`} className="flex items-center gap-2.5">
          <Dot urgent={s.priority === "urgent"} />
          <span className="font-mono text-[12.5px] font-medium group-hover:text-accent">
            {s.accession}
          </span>
        </Link>
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
          {danger > 0 && (
            <Chip tone="resistant">
              <span className="font-mono text-[10px]" aria-hidden>
                !
              </span>
              Lookup fails ×{danger}
            </Chip>
          )}
          {deferred > 0 && (
            <Chip tone="deferred">
              <span className="font-mono text-[10px]" aria-hidden>
                ?
              </span>
              {deferred} deferred
            </Chip>
          )}
          {danger === 0 && deferred === 0 && <span className="text-[12px] text-faint">—</span>}
        </div>
      </td>
      <td className="tnum px-5 py-3.5 font-mono text-[12px] text-muted">{relTime(s.receivedAt)}</td>
    </tr>
  );
}
