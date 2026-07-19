"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/Rail";
import { Alert, Button, Card, SectionLabel } from "@/components/ui";
import { useSpecimens, useThresholds } from "@/lib/store";
import { DEFAULT_THRESHOLDS } from "@/lib/types";

/** Thresholds are a clinical judgement, not a hyperparameter.
 *
 *  The two errors are not symmetric — calling a drug susceptible when it is resistant can kill,
 *  while the reverse wastes a last-resort drug — so the band is not centred on 0.5 and the person
 *  who owns that trade-off should be able to see and set it. Changing it re-scores every specimen
 *  live, so the cost of widening the band is visible before it is accepted.
 */
export default function Settings() {
  const [t, setT] = useThresholds();
  const { rows, reset } = useSpecimens();

  const preview = useMemo(() => {
    let answered = 0;
    let deferred = 0;
    let risky = 0; // confident susceptible calls, the direction that can harm
    for (const s of rows) {
      for (const d of s.drugs) {
        const inBand = d.probability >= t.abstainLow && d.probability <= t.abstainHigh;
        const novelty =
          t.noveltyBlocksSusceptible && d.reason?.includes("unrecognised") && d.probability <= 0.5;
        if (inBand || novelty) deferred++;
        else {
          answered++;
          if (d.probability <= 0.5) risky++;
        }
      }
    }
    const total = answered + deferred;
    return { answered, deferred, risky, rate: total ? deferred / total : 0 };
  }, [rows, t]);

  const wide = t.abstainHigh - t.abstainLow;

  return (
    <>
      <PageHeader
        title="Settings"
        sub="Operating parameters for this laboratory. These are clinical decisions, not tuning knobs, and every change is previewed against the current caseload before it takes effect."
      />

      <div className="grid grid-cols-[1fr_340px] gap-5">
        <div className="space-y-5">
          <Card>
            <SectionLabel>Abstention band</SectionLabel>
            <p className="mb-5 max-w-[74ch] text-[12.5px] leading-relaxed text-muted">
              Results falling inside this probability band are deferred to culture rather than reported.
              The band is deliberately not centred on 0.5: calling a drug susceptible when it is resistant
              puts a patient on ineffective therapy, while the reverse only wastes a broader agent.
            </p>

            <div className="space-y-6">
              <Slider
                label="Lower bound"
                hint="Below this, a susceptible call is reported"
                value={t.abstainLow}
                min={0.1}
                max={0.5}
                onChange={(v) => setT({ ...t, abstainLow: Math.min(v, t.abstainHigh - 0.05) })}
              />
              <Slider
                label="Upper bound"
                hint="Above this, a resistant call is reported"
                value={t.abstainHigh}
                min={0.5}
                max={0.9}
                onChange={(v) => setT({ ...t, abstainHigh: Math.max(v, t.abstainLow + 0.05) })}
              />
            </div>

            <div className="mt-6 flex h-3 overflow-hidden rounded-full">
              <div className="bg-susceptible" style={{ width: `${t.abstainLow * 100}%` }} />
              <div className="bg-deferred/60" style={{ width: `${wide * 100}%` }} />
              <div className="bg-resistant" style={{ width: `${(1 - t.abstainHigh) * 100}%` }} />
            </div>
            <div className="mt-1.5 flex justify-between font-mono text-[11px] text-faint">
              <span>0.00 susceptible</span>
              <span>deferred {(wide * 100).toFixed(0)}% of range</span>
              <span>resistant 1.00</span>
            </div>
          </Card>

          <Card>
            <SectionLabel>Safety gates</SectionLabel>
            <div className="space-y-3">
              <Toggle
                on={t.noveltyBlocksSusceptible}
                onChange={(v) => setT({ ...t, noveltyBlocksSusceptible: v })}
                label="Unrecognised machinery blocks a susceptible call"
                hint="At any confidence. The probability was computed without that evidence, so a low number reflects what the model could see, not what is there. Does not block a resistant call."
              />
              <Toggle
                on={t.sparseGate}
                onChange={(v) => setT({ ...t, sparseGate: v })}
                label="Defer on implausibly sparse genomes"
                hint="Across 7,276 real genomes only 4 carry zero determinants and the median is 13. A near-empty vector signals a truncated assembly, not a clean organism."
              />
              <Toggle
                on={t.coherenceGate}
                onChange={(v) => setT({ ...t, coherenceGate: v })}
                label="Defer when a call contradicts the isolate's own profile"
                hint="Compares the prediction against what the nearest training isolates actually did."
              />
            </div>
            {!t.noveltyBlocksSusceptible && (
              <div className="mt-4">
                <Alert title="Safety gate disabled">
                  With this gate off, a genome carrying a resistance mechanism the model has never seen can
                  receive a confident susceptible call. This is the failure mode the system was built to
                  prevent — on our benchmark it produced 12 lethal errors out of 12 cases.
                </Alert>
              </div>
            )}
          </Card>

          <Card>
            <SectionLabel>Demonstration data</SectionLabel>
            <p className="mb-4 max-w-[74ch] text-[12.5px] leading-relaxed text-muted">
              This build stores review state in your browser so the whole workflow runs without a backend.
              Resetting restores the seeded caseload and discards any releases or overrides you have
              recorded.
            </p>
            <Button variant="ghost" onClick={reset}>
              Reset demonstration data
            </Button>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="sticky top-7">
            <SectionLabel>Effect on the current caseload</SectionLabel>
            <div className="mb-5">
              <div className="tnum font-mono text-[34px] leading-none font-semibold text-deferred">
                {Math.round(preview.rate * 100)}%
              </div>
              <div className="mt-1.5 text-[12px] text-muted">of results would be deferred to culture</div>
            </div>
            <div className="space-y-2.5 text-[12.5px]">
              {[
                ["Answered", preview.answered],
                ["Deferred", preview.deferred],
                ["Susceptible calls reported", preview.risky],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-line pb-2 last:border-0">
                  <span className="text-muted">{k}</span>
                  <span className="tnum font-mono font-medium">{v}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-[11.5px] leading-relaxed text-faint">
              Widening the band defers more and reports less. Narrowing it reports more, including more
              susceptible calls — which is the direction that can reach a patient on ineffective therapy.
            </p>
            <Button
              variant="ghost"
              className="mt-4 w-full"
              onClick={() => setT(DEFAULT_THRESHOLDS)}
            >
              Restore clinical defaults
            </Button>
          </Card>
        </div>
      </div>
    </>
  );
}

function Slider({
  label,
  hint,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <label className="text-[12.5px] font-medium">{label}</label>
        <span className="tnum font-mono text-[13px] font-medium">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={0.01}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="accent-accent w-full"
      />
      <p className="mt-1 text-[11.5px] text-faint">{hint}</p>
    </div>
  );
}

function Toggle({
  on,
  onChange,
  label,
  hint,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <div className="flex gap-3.5 rounded-[10px] border border-line p-3.5">
      <button
        role="switch"
        aria-checked={on}
        onClick={() => onChange(!on)}
        className={`mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition-colors duration-200 ${
          on ? "bg-accent" : "bg-line-strong"
        }`}
      >
        <span
          className={`block size-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
            on ? "translate-x-4" : ""
          }`}
        />
      </button>
      <div className="min-w-0">
        <div className="text-[12.5px] font-medium">{label}</div>
        <p className="mt-1 text-[11.5px] leading-relaxed text-faint">{hint}</p>
      </div>
    </div>
  );
}
