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

/** Worklist flags answer one question: can the clinician act on this specimen now?
 *
 *  Two earlier versions got this wrong. The first flagged "genotype lookup would fail here",
 *  which is a claim about a competing method — useful when evaluating the system, useless when
 *  working a bench. The second flagged every deferred drug, which fired on nearly every specimen:
 *  with ~19% of results deferred and ten drugs each, P(at least one) is about 88%. Framing that as
 *  a warning implied the specimen still needed culture and erased the point of the system.
 *
 *  What matters is whether a usable therapy option came back confidently. Nine confident calls and
 *  one deferral is a success, not a caveat.
 */
function triage(s: Specimen) {
  const flags: { label: string; tone: "resistant" | "accent" | "susceptible"; glyph: string }[] = [];
  const options = s.drugs.filter((d) => d.call === "SUSCEPTIBLE");

  if (options.length > 0)
    flags.push({
      label: `${options.length} option${options.length > 1 ? "s" : ""} available`,
      tone: "susceptible",
      glyph: "✓",
    });
  else flags.push({ label: "No option available", tone: "resistant", glyph: "!" });

  // Rare and genuinely actionable, so it survives the cull.
  if (s.drugs.some((d) => d.reason?.includes("unrecognised")))
    flags.push({ label: "Unrecognised machinery", tone: "accent", glyph: "◆" });

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

      <div className="stagger mb-6 grid grid-cols-4 items-stretch gap-4">
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
            value={`${rows.filter((s) => s.drugs.some((d) => d.call === "SUSCEPTIBLE")).length}/${rows.length}`}
            label="with a usable therapy option now"
            note={`${Math.round(META.deferral.mean_deferral * 100)}% of individual results pending culture`}
          />,
          <Stat
            key="d"
            value={META.deferral.answered_accuracy.toFixed(3)}
            label="accuracy on answered cases"
            note={`+${META.deferral.accuracy_gain} vs forced answer`}
          />,
        ].map((el, i) => (
          <div key={i} className="h-full" style={{ animationDelay: `${i * 45}ms` }}>
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

        <table className="w-full table-fixed">
          <thead>
            <tr className="border-b border-line">
              {[
                ["Accession", "w-[158px]"],
                ["Organism", "w-auto"],
                ["Source", "w-[126px]"],
                ["Ward", "w-[168px]"],
                ["Status", "w-[122px]"],
                ["Therapy", "w-[196px]"],
                ["Received", "w-[98px]"],
              ].map(([h, w]) => (
                <th
                  key={h}
                  className={`px-5 py-2.5 text-left text-[11.5px] font-semibold text-faint ${w}`}
                >
                  {h}
                </th>
              ))}
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
          <span className="font-mono text-[12.5px] font-medium whitespace-nowrap group-hover:text-accent">
            {s.accession}
          </span>
        </span>
      </td>
      <td className="truncate px-5 py-3.5 text-[13px] italic">{s.organism}</td>
      <td className="truncate px-5 py-3.5 text-[13px] text-muted">{s.source}</td>
      <td className="truncate px-5 py-3.5 text-[13px] whitespace-nowrap text-muted">{s.ward}</td>
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
