"use client";

import Link from "next/link";
import { useMemo } from "react";
import { PageHeader } from "@/components/Rail";
import { CallChip, Card, Chip, SectionLabel, Stat, relTime } from "@/components/ui";
import { useSpecimens } from "@/lib/store";

/** Reconciliation closes the loop.
 *
 *  Two days after we predict, the culture result actually arrives. Capturing it turns the
 *  system's accuracy from a claim made once into something the laboratory re-measures on its own
 *  patients, continuously. It is also how a lab would decide whether to keep trusting us.
 */
export default function Reconciliation() {
  const { rows } = useSpecimens();

  const cases = useMemo(() => {
    const out: {
      accession: string;
      id: string;
      drug: string;
      predicted: string;
      culture: string;
      agree: boolean;
      deferred: boolean;
      receivedAt: string;
    }[] = [];
    for (const s of rows) {
      if (s.status !== "reconciled") continue;
      for (const d of s.drugs) {
        if (!d.cultureResult) continue;
        const predicted = d.call;
        const culture = d.cultureResult.toUpperCase();
        out.push({
          accession: s.accession,
          id: s.id,
          drug: d.drug,
          predicted,
          culture,
          agree: predicted === culture,
          deferred: predicted === "INDETERMINATE",
          receivedAt: s.receivedAt,
        });
      }
    }
    return out;
  }, [rows]);

  const answered = cases.filter((c) => !c.deferred);
  const agreed = answered.filter((c) => c.agree).length;
  const concordance = answered.length ? agreed / answered.length : 0;
  const deferredCount = cases.filter((c) => c.deferred).length;
  // A deferral is "justified" when culture came back resistant — we declined rather than risk a
  // confident susceptible call on a genuinely resistant isolate.
  const deferredResistant = cases.filter((c) => c.deferred && c.culture === "RESISTANT").length;
  const missed = answered.filter((c) => !c.agree && c.predicted === "SUSCEPTIBLE").length;

  const awaiting = rows.filter((s) => s.status === "released").length;

  return (
    <>
      <PageHeader
        title="Reconciliation"
        sub="Culture susceptibility results arrive 48–72 hours after we predict. Comparing them turns accuracy from a claim into something this laboratory re-measures on its own patients."
      />

      <div className="stagger mb-6 grid grid-cols-4 gap-4">
        <Stat
          value={`${Math.round(concordance * 100)}%`}
          label="concordance with culture on answered calls"
          note={`${agreed} of ${answered.length}`}
        />
        <Stat value={awaiting} label="released, awaiting culture result" tone="deferred" />
        <Stat
          value={deferredCount}
          label="deferred to culture"
          note={`${deferredResistant} were resistant — deferral justified`}
        />
        <Stat
          value={missed}
          label="called susceptible, culture said resistant"
          note="the error that matters"
          tone={missed > 0 ? "resistant" : undefined}
        />
      </div>

      <Card pad={false} className="overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
          <h2 className="text-[14.5px] font-semibold">Prediction versus culture</h2>
          <span className="text-[12px] text-faint">{cases.length} paired results</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line">
                {["Accession", "Antibiotic", "We predicted", "Culture said", "Outcome", "Received"].map(
                  (h) => (
                    <th key={h} className="px-5 py-2.5 text-left text-[11.5px] font-semibold text-faint">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {cases.map((c, i) => (
                <tr key={i} className="border-b border-line last:border-0 hover:bg-surface-2">
                  <td className="px-5 py-3">
                    <Link
                      href={`/specimen/${c.id}`}
                      className="font-mono text-[12.5px] hover:text-accent"
                    >
                      {c.accession}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-[13px]">{c.drug}</td>
                  <td className="px-5 py-3">
                    <CallChip call={c.predicted as "RESISTANT" | "SUSCEPTIBLE" | "INDETERMINATE"} size="sm" />
                  </td>
                  <td className="px-5 py-3">
                    <CallChip call={c.culture as "RESISTANT" | "SUSCEPTIBLE"} size="sm" />
                  </td>
                  <td className="px-5 py-3">
                    {c.deferred ? (
                      <Chip tone="deferred">
                        <span className="font-mono text-[10px]" aria-hidden>
                          ?
                        </span>
                        Deferred{c.culture === "RESISTANT" ? " · justified" : ""}
                      </Chip>
                    ) : c.agree ? (
                      <Chip tone="susceptible">
                        <span className="font-mono text-[10px]" aria-hidden>
                          ✓
                        </span>
                        Concordant
                      </Chip>
                    ) : (
                      <Chip tone="resistant">
                        <span className="font-mono text-[10px]" aria-hidden>
                          ✗
                        </span>
                        {c.predicted === "SUSCEPTIBLE" ? "Missed resistance" : "Over-called"}
                      </Chip>
                    )}
                  </td>
                  <td className="tnum px-5 py-3 font-mono text-[12px] text-muted">
                    {relTime(c.receivedAt)}
                  </td>
                </tr>
              ))}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-[13px] text-faint">
                    No culture results have been returned yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="mt-6">
        <SectionLabel>Why this page exists</SectionLabel>
        <p className="max-w-[82ch] text-[12.5px] leading-relaxed text-muted">
          A validation figure computed once, on a public dataset, tells a laboratory very little about its
          own population. Reconciliation re-derives it continuously from the specimens actually passing
          through this bench — and separates the two failure modes that matter. A deferral followed by a
          resistant culture is the system working: it declined rather than risk a confident susceptible
          call. A <b className="text-ink">susceptible call</b> followed by a resistant culture is the one
          that reaches a patient, and it is counted on its own.
        </p>
      </Card>
    </>
  );
}
