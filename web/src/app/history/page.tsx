"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Rail";
import { Card, Chip, relTime } from "@/components/ui";
import { useSpecimens } from "@/lib/store";

export default function History() {
  const { rows } = useSpecimens();
  const [q, setQ] = useState("");

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(
      (s) =>
        s.accession.toLowerCase().includes(needle) ||
        s.ward.toLowerCase().includes(needle) ||
        s.source.toLowerCase().includes(needle) ||
        s.requestedBy.toLowerCase().includes(needle) ||
        s.determinants.some((d) => d.toLowerCase().includes(needle)) ||
        s.drugs.some((d) => d.drug.toLowerCase().includes(needle)),
    );
  }, [rows, q]);

  return (
    <>
      <PageHeader
        title="History"
        sub="Every specimen this laboratory has analysed, with the full audit trail behind each one."
      />

      <div className="mb-5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search accession, ward, clinician, antibiotic or determinant…"
          className="w-full max-w-[520px] rounded-[10px] border border-line bg-surface px-3.5 py-2.5 text-[13px] outline-none focus:border-accent"
        />
      </div>

      <div className="stagger space-y-3">
        {shown.map((s) => {
          const danger = s.drugs.filter((d) => d.lookupDangerouslyWrong).length;
          const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE").length;
          const resistant = s.drugs.filter((d) => d.call === "RESISTANT").length;
          return (
            <Card key={s.id} className="transition-shadow duration-200 hover:shadow-md">
              <div className="flex flex-wrap items-center gap-4">
                <Link href={`/specimen/${s.id}`} className="font-mono text-[13px] font-medium hover:text-accent">
                  {s.accession}
                </Link>
                <span className="text-[12.5px] text-muted">
                  {s.source} · {s.ward} · {s.requestedBy}
                </span>
                <div className="ml-auto flex flex-wrap gap-1.5">
                  <Chip tone="resistant">{resistant} resistant</Chip>
                  {deferred > 0 && <Chip tone="deferred">{deferred} deferred</Chip>}
                  {danger > 0 && <Chip tone="resistant">lookup fails ×{danger}</Chip>}
                  <Chip tone={s.status === "reconciled" ? "susceptible" : "neutral"}>{s.status}</Chip>
                </div>
              </div>
              <ol className="mt-3.5 flex flex-wrap gap-x-6 gap-y-1.5 border-t border-line pt-3">
                {s.audit.map((a, i) => (
                  <li key={i} className="text-[11.5px] text-muted">
                    <span className="tnum font-mono text-faint">{a.at.replace("T", " ")}</span>{" "}
                    {a.action}
                    <span className="text-faint"> · {a.who}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-2 text-[11.5px] text-faint">Received {relTime(s.receivedAt)}</div>
            </Card>
          );
        })}
        {shown.length === 0 && (
          <Card>
            <p className="py-8 text-center text-[13px] text-faint">Nothing matches that search.</p>
          </Card>
        )}
      </div>
    </>
  );
}
