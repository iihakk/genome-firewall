"use client";

import Link from "next/link";
import { PageHeader } from "@/components/Rail";
import { Alert, Button, CallChip, Card, Chip, SectionLabel, relTime } from "@/components/ui";
import { CURRENT_USER, useSpecimens } from "@/lib/store";

/** The review queue. Nothing reaches a treating clinician without passing through here. */
export default function Review() {
  const { rows, release } = useSpecimens();
  const queue = rows.filter((s) => s.status === "review");

  return (
    <>
      <PageHeader
        title="Awaiting review"
        sub="Analyses complete, pending sign-out by a qualified reviewer. Releasing is a clinical act and is recorded against your name."
      />

      {queue.length === 0 ? (
        <Card>
          <p className="py-10 text-center text-[13px] text-faint">
            The review queue is clear.
          </p>
        </Card>
      ) : (
        <div className="stagger space-y-4">
          {queue.map((s) => {
            const danger = s.drugs.filter((d) => d.lookupDangerouslyWrong);
            const deferred = s.drugs.filter((d) => d.call === "INDETERMINATE");
            return (
              <Card key={s.id}>
                <div className="mb-4 flex flex-wrap items-start gap-4">
                  <div>
                    <Link href={`/specimen/${s.id}`} className="font-mono text-[15px] font-semibold hover:text-accent">
                      {s.accession}
                    </Link>
                    <div className="mt-1 text-[12.5px] text-muted">
                      {s.organism} · {s.source} · {s.ward} · requested by {s.requestedBy}
                    </div>
                  </div>
                  <div className="ml-auto flex gap-2.5">
                    <Link href={`/specimen/${s.id}`}>
                      <Button variant="ghost">Open</Button>
                    </Link>
                    <Button onClick={() => release(s.id, CURRENT_USER)}>Verify &amp; release</Button>
                  </div>
                </div>

                {danger.length > 0 && (
                  <div className="mb-4">
                    <Alert title="Requires attention before release">
                      For <b>{danger.map((d) => d.drug).join(", ")}</b>, a genotype lookup would report
                      susceptible. This isolate is resistant.
                    </Alert>
                  </div>
                )}

                <SectionLabel>Calls</SectionLabel>
                <div className="flex flex-wrap gap-2">
                  {s.drugs.map((d) => (
                    <span key={d.drug} className="flex items-center gap-1.5 rounded-[10px] border border-line px-2.5 py-1.5">
                      <span className="text-[12px]">{d.drug}</span>
                      <CallChip call={d.call} size="sm" />
                    </span>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-3.5 text-[12px] text-muted">
                  <span>Received {relTime(s.receivedAt)}</span>
                  {deferred.length > 0 && (
                    <Chip tone="deferred">{deferred.length} deferred to culture</Chip>
                  )}
                  <span className="ml-auto">
                    Reviewer · {CURRENT_USER} · <b className="text-deferred">not yet signed</b>
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
