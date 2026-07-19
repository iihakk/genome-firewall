"use client";

import { PageHeader } from "@/components/Rail";
import { Card, Chip, SectionLabel, Stat } from "@/components/ui";
import { META } from "@/lib/store";
import { EXCLUDED_DRUGS } from "@/lib/types";

const TIERS: { key: string; label: string; note: string }[] = [
  { key: "random", label: "Random split", note: "the optimistic baseline most work reports" },
  { key: "clone", label: "Clone-aware", note: "identical genotype profiles never straddle the split" },
  { key: "holdout", label: "Locked holdout", note: "quarantined before modelling, used once" },
  { key: "external", label: "External", note: "different curation and no mutation features" },
  { key: "temporal", label: "Temporal", note: "trained on the past, tested on the future" },
  { key: "geographic", label: "Geographic", note: "trained on some countries, tested on others" },
];

export default function Validation() {
  const v = META.validation;
  const d = META.discordance;
  const f = META.deferral;
  const drugs = Object.entries(META.perDrug)
    .filter(([, m]) => m.rule_balanced_acc != null && m.model_balanced_acc != null)
    .sort(
      (a, b) =>
        (b[1].model_balanced_acc! - b[1].rule_balanced_acc!) -
        (a[1].model_balanced_acc! - a[1].rule_balanced_acc!),
    );

  return (
    <>
      <PageHeader
        title="Model & validation"
        sub="What this system is measured to do, and where it fails. Every figure is produced by the pipeline in this repository and reproducible from a clean checkout."
      />

      {/* headline */}
      <SectionLabel>Where clinical lookup fails</SectionLabel>
      <div className="stagger mb-3 grid grid-cols-4 gap-4">
        <Stat
          value={d.false_susceptible.toLocaleString()}
          label="isolates where a genotype lookup reports the drug will work — and it will not"
          tone="resistant"
        />
        <Stat value={d.recovered.toLocaleString()} label="of those, correctly called resistant here" />
        <Stat value={`${Math.round(d.recovery_rate * 100)}%`} label="recovery rate on the dangerous failures" />
        <Stat
          value={d.false_resistant.toLocaleString()}
          label="isolates where lookup discards a drug that would have worked"
          tone="deferred"
        />
      </div>
      <Card className="mb-8">
        <SectionLabel>Mechanisms a gene-presence rule cannot express</SectionLabel>
        <div className="space-y-2.5">
          {Object.entries(d.mechanisms)
            .sort((a, b) => b[1] - a[1])
            .map(([k, n]) => {
              const pct = Math.round((100 * n) / d.false_susceptible);
              return (
                <div key={k} className="grid grid-cols-[190px_1fr_84px] items-center gap-4">
                  <span className="text-[12.5px]">{k}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="animate-grow h-full rounded-full bg-resistant/70"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="tnum text-right font-mono text-[12px] text-muted">
                    {n.toLocaleString()} · {pct}%
                  </span>
                </div>
              );
            })}
        </div>
        <p className="mt-4 max-w-[80ch] text-[12.5px] leading-relaxed text-muted">
          This is the argument for the system. Not that it is more accurate on average, but that it sees
          mechanisms current practice is structurally blind to.
        </p>
      </Card>

      {/* tiers */}
      <SectionLabel>Six validation tiers</SectionLabel>
      <Card className="mb-8">
        <p className="mb-5 max-w-[78ch] text-[12.5px] leading-relaxed text-muted">
          Each tier removes a different crutch. A model that holds up only on the first is doing recall,
          not biology. We report the lower numbers.
        </p>
        <div className="space-y-3.5">
          {TIERS.map((t) => {
            const val = v.mean[t.key];
            if (val == null) return null;
            const external = ["external", "temporal", "geographic"].includes(t.key);
            return (
              <div key={t.key} className="grid grid-cols-[270px_1fr_62px] items-center gap-4">
                <div>
                  <div className="text-[12.5px] font-medium">{t.label}</div>
                  <div className="text-[11px] text-faint">{t.note}</div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`animate-grow h-full rounded-full ${external ? "bg-deferred" : "bg-accent"}`}
                    style={{ width: `${((val - 0.5) / 0.5) * 100}%` }}
                  />
                </div>
                <span className="tnum text-right font-mono text-[13px] font-medium">{val.toFixed(3)}</span>
              </div>
            );
          })}
        </div>
        <p className="mt-5 max-w-[78ch] text-[12px] leading-relaxed text-faint">
          The external tier trains on NCBI Pathogen Detection with mutation features and tests on BV-BRC
          without them, so it measures cross-curation transfer and feature degradation at the same time.
          It is the number we consider load-bearing.
        </p>
      </Card>

      {/* per drug */}
      <SectionLabel>Against the clinical rule, per antibiotic</SectionLabel>
      <Card pad={false} className="mb-8 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line">
                {["Antibiotic", "n", "Rule", "Model", "Delta", "External AUC", "Status"].map((h, i) => (
                  <th
                    key={h}
                    className={`px-5 py-2.5 text-[11.5px] font-semibold text-faint ${i > 0 && i < 6 ? "text-right" : "text-left"}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {drugs.map(([name, m]) => {
                const delta = m.model_balanced_acc! - m.rule_balanced_acc!;
                const excl = EXCLUDED_DRUGS[name];
                return (
                  <tr key={name} className="border-b border-line last:border-0 hover:bg-surface-2">
                    <td className="px-5 py-3 text-[13px]">{name}</td>
                    <td className="tnum px-5 py-3 text-right font-mono text-[12px] text-muted">{m.n}</td>
                    <td className="tnum px-5 py-3 text-right font-mono text-[12px] text-muted">
                      {m.rule_balanced_acc!.toFixed(3)}
                    </td>
                    <td className="tnum px-5 py-3 text-right font-mono text-[12px] font-medium">
                      {m.model_balanced_acc!.toFixed(3)}
                    </td>
                    <td
                      className={`tnum px-5 py-3 text-right font-mono text-[12px] ${
                        delta > 0.02 ? "text-susceptible" : delta < -0.02 ? "text-resistant" : "text-faint"
                      }`}
                    >
                      {delta > 0 ? "+" : ""}
                      {delta.toFixed(3)}
                    </td>
                    <td className="tnum px-5 py-3 text-right font-mono text-[12px] text-muted">
                      {m.external != null ? m.external.toFixed(3) : "—"}
                    </td>
                    <td className="px-5 py-3">
                      {excl ? (
                        <span title={excl}>
                          <Chip tone="deferred">
                            <span className="font-mono text-[10px]" aria-hidden>
                              ⚠
                            </span>
                            Restricted
                          </Chip>
                        </span>
                      ) : (
                        <Chip tone="susceptible">
                          <span className="font-mono text-[10px]" aria-hidden>
                            ✓
                          </span>
                          Approved
                        </Chip>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mb-8 grid grid-cols-2 gap-5">
        <Card>
          <SectionLabel>What abstention buys</SectionLabel>
          <div className="space-y-2.5 text-[12.5px]">
            {[
              ["Deferral rate", `${Math.round(f.mean_deferral * 100)}%`],
              ["Accuracy on answered cases", f.answered_accuracy.toFixed(3)],
              ["Accuracy if forced to answer", f.accuracy_if_forced.toFixed(3)],
              ["Bought by knowing when to stop", `+${f.accuracy_gain.toFixed(3)}`],
            ].map(([k, val]) => (
              <div key={k} className="flex justify-between border-b border-line pb-2 last:border-0">
                <span className="text-muted">{k}</span>
                <span className="tnum font-mono font-medium">{val}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
            {f.lethal_errors} confident-susceptible errors remain across {f.predictions.toLocaleString()}{" "}
            predictions on quarantined isolates. Reported because it is the error that matters clinically,
            and it is not zero.
          </p>
        </Card>

        <Card>
          <SectionLabel>Restricted and excluded</SectionLabel>
          <div className="space-y-3">
            {Object.entries(EXCLUDED_DRUGS).map(([drug, why]) => (
              <div key={drug} className="rounded-[10px] bg-deferred-soft p-3 ring-1 ring-deferred-line">
                <div className="mb-1 text-[12.5px] font-medium text-deferred">{drug}</div>
                <p className="text-[12px] leading-relaxed text-ink/75">{why}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <SectionLabel>Provenance</SectionLabel>
      <Card>
        <dl className="space-y-2.5 text-[12.5px]">
          {Object.entries(META.provenance).map(([k, val]) => (
            <div key={k} className="flex gap-4 border-b border-line pb-2.5 last:border-0">
              <dt className="w-[150px] shrink-0 text-faint capitalize">{k.replace(/_/g, " ")}</dt>
              <dd className="text-muted">{String(val)}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </>
  );
}
