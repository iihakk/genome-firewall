"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/Rail";
import { Card, Chip, SectionLabel, Stat, prettyToken } from "@/components/ui";
import { useSpecimens } from "@/lib/store";

/** The cumulative antibiogram.
 *
 *  Laboratories publish one of these annually and it drives empiric prescribing policy for the
 *  whole hospital. Because every specimen here is already analysed, it can be produced
 *  continuously rather than once a year — and deferrals are shown rather than hidden, since a
 *  susceptibility rate computed only over confident calls would flatter itself.
 */
export default function Surveillance() {
  const { rows } = useSpecimens();

  const byDrug = useMemo(() => {
    const m = new Map<string, { r: number; s: number; d: number }>();
    for (const sp of rows) {
      for (const dr of sp.drugs) {
        const e = m.get(dr.drug) ?? { r: 0, s: 0, d: 0 };
        if (dr.call === "RESISTANT") e.r++;
        else if (dr.call === "SUSCEPTIBLE") e.s++;
        else e.d++;
        m.set(dr.drug, e);
      }
    }
    return [...m.entries()]
      .map(([drug, e]) => ({
        drug,
        ...e,
        total: e.r + e.s + e.d,
        called: e.r + e.s,
        pctS: e.r + e.s ? e.s / (e.r + e.s) : 0,
      }))
      .sort((a, b) => a.pctS - b.pctS);
  }, [rows]);

  const determinants = useMemo(() => {
    const m = new Map<string, number>();
    for (const sp of rows) for (const t of sp.determinants) m.set(t, (m.get(t) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 18);
  }, [rows]);

  const byWard = useMemo(() => {
    const m = new Map<string, { n: number; res: number }>();
    for (const sp of rows) {
      const e = m.get(sp.ward) ?? { n: 0, res: 0 };
      e.n++;
      if (sp.drugs.some((d) => d.drug === "meropenem" && d.call === "RESISTANT")) e.res++;
      m.set(sp.ward, e);
    }
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [rows]);

  const mero = byDrug.find((d) => d.drug === "meropenem");

  return (
    <>
      <PageHeader
        title="Surveillance"
        sub="A cumulative antibiogram built from every specimen this laboratory has analysed. Published annually in most labs; produced continuously here."
      />

      <div className="stagger mb-6 grid grid-cols-4 gap-4">
        <Stat value={rows.length} label="isolates in the current period" />
        <Stat
          value={`${Math.round((mero?.pctS ?? 0) * 100)}%`}
          label="meropenem-susceptible among called isolates"
          tone={(mero?.pctS ?? 0) < 0.4 ? "resistant" : undefined}
        />
        <Stat
          value={determinants.filter(([t]) => t.startsWith("POINT:") || t.startsWith("TRUNC:")).length}
          label="distinct mutation or truncation mechanisms circulating"
        />
        <Stat
          value={rows.filter((s) => s.determinants.some((t) => t === "blakpc")).length}
          label="isolates carrying a KPC carbapenemase"
          tone="resistant"
        />
      </div>

      <Card className="mb-6">
        <SectionLabel>Susceptibility by antibiotic</SectionLabel>
        <p className="mb-5 max-w-[80ch] text-[12.5px] text-muted">
          Bars show the proportion of <i>called</i> isolates that were susceptible. Deferred results are
          shown separately rather than dropped — a susceptibility rate computed only over confident calls
          would flatter itself.
        </p>
        <div className="space-y-3">
          {byDrug.map((d) => (
            <div key={d.drug} className="grid grid-cols-[212px_1fr_150px] items-center gap-4">
              <span className="text-[12.5px]">{d.drug}</span>
              <div className="flex h-3 overflow-hidden rounded-full bg-surface-2">
                <div
                  className="animate-grow h-full bg-susceptible"
                  style={{ width: `${(d.s / d.total) * 100}%` }}
                  title={`${d.s} susceptible`}
                />
                <div
                  className="animate-grow h-full bg-resistant"
                  style={{ width: `${(d.r / d.total) * 100}%` }}
                  title={`${d.r} resistant`}
                />
                <div
                  className="animate-grow h-full bg-deferred/55"
                  style={{ width: `${(d.d / d.total) * 100}%` }}
                  title={`${d.d} deferred`}
                />
              </div>
              <span className="tnum text-right font-mono text-[11.5px] text-muted">
                {Math.round(d.pctS * 100)}% S · {d.d > 0 ? `${d.d} def` : "—"}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-5 flex gap-4 text-[11.5px] text-faint">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-susceptible" /> susceptible
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-resistant" /> resistant
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-deferred/55" /> deferred to culture
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-5">
        <Card>
          <SectionLabel>Circulating determinants</SectionLabel>
          <div className="space-y-2">
            {determinants.map(([t, n]) => (
              <div key={t} className="grid grid-cols-[1fr_92px_36px] items-center gap-3">
                <span className="truncate font-mono text-[11.5px]">{prettyToken(t)}</span>
                <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`animate-grow h-full rounded-full ${
                      t.startsWith("POINT:") || t.startsWith("TRUNC:") ? "bg-resistant/70" : "bg-accent/60"
                    }`}
                    style={{ width: `${(n / rows.length) * 100}%` }}
                  />
                </div>
                <span className="tnum text-right font-mono text-[11px] text-muted">{n}</span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-[11.5px] leading-relaxed text-faint">
            Red bars are mutations and truncations. They spread differently from plasmid-borne genes and
            are invisible to gene-presence surveillance.
          </p>
        </Card>

        <Card>
          <SectionLabel>Carbapenem resistance by ward</SectionLabel>
          <div className="space-y-2.5">
            {byWard.map(([ward, e]) => (
              <div key={ward} className="grid grid-cols-[152px_1fr_60px] items-center gap-3">
                <span className="truncate text-[12.5px]">{ward}</span>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="animate-grow h-full rounded-full bg-resistant/70"
                    style={{ width: `${(e.res / Math.max(e.n, 1)) * 100}%` }}
                  />
                </div>
                <span className="tnum text-right font-mono text-[11.5px] text-muted">
                  {e.res}/{e.n}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-1.5">
            <Chip tone="deferred">Small denominators — indicative only</Chip>
          </div>
        </Card>
      </div>
    </>
  );
}
