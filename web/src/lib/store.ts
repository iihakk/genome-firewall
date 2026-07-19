"use client";

/** Client-side store.
 *
 * Browser-local by design for this build: the whole workflow — review, override, sign-out,
 * reconciliation — runs without a backend, so the demo cannot fail on a network call and works
 * offline. A production deployment replaces this with the laboratory's LIS; the interfaces below
 * are what that adapter would implement.
 */

import { useCallback, useEffect, useState } from "react";
import seed from "@/data/seed.json";
import type { Call, Specimen, Thresholds } from "./types";
import { DEFAULT_THRESHOLDS } from "./types";

const KEY = "gf.specimens.v1";
const KEY_T = "gf.thresholds.v1";

type Seed = typeof seed;
export const META = {
  validation: seed.validation,
  perDrug: seed.perDrug,
  discordance: seed.discordance,
  deferral: seed.deferral,
  provenance: seed.provenance,
  note: seed.note,
} as unknown as {
  validation: { mean: Record<string, number>; rule: Record<string, number> };
  perDrug: Record<string, Record<string, number | null>>;
  discordance: {
    false_susceptible: number;
    recovered: number;
    recovery_rate: number;
    false_resistant: number;
    mechanisms: Record<string, number>;
  };
  deferral: {
    mean_deferral: number;
    answered_accuracy: number;
    accuracy_if_forced: number;
    accuracy_gain: number;
    lethal_errors: number;
    predictions: number;
  };
  provenance: Record<string, string | number>;
  note: string;
};

function load(): Specimen[] {
  if (typeof window === "undefined") return seed.specimens as unknown as Specimen[];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Specimen[];
  } catch {
    /* corrupted or unavailable storage falls through to the seed */
  }
  return seed.specimens as unknown as Specimen[];
}

function save(rows: Specimen[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(rows));
  } catch {
    /* private browsing — the session still works, it just will not persist */
  }
}

/** Broadcast so every mounted view reflects a change immediately. */
const EVT = "gf:changed";
const emit = () => window.dispatchEvent(new Event(EVT));

export function useSpecimens() {
  const [rows, setRows] = useState<Specimen[]>(() => seed.specimens as unknown as Specimen[]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setRows(load());
    setReady(true);
    const h = () => setRows(load());
    window.addEventListener(EVT, h);
    return () => window.removeEventListener(EVT, h);
  }, []);

  const update = useCallback((id: string, fn: (s: Specimen) => Specimen) => {
    const next = load().map((s) => (s.id === id ? fn(s) : s));
    save(next);
    setRows(next);
    emit();
  }, []);

  const release = useCallback(
    (id: string, who: string) =>
      update(id, (s) => ({
        ...s,
        status: "released",
        releasedBy: who,
        releasedAt: new Date().toISOString().slice(0, 16),
        audit: [
          ...s.audit,
          {
            at: new Date().toISOString().slice(0, 16),
            who,
            action: "Verified and released",
            detail: "All calls reviewed; deferrals referred to culture",
          },
        ],
      })),
    [update],
  );

  const override = useCallback(
    (id: string, drug: string, to: Call, reason: string, who: string) =>
      update(id, (s) => ({
        ...s,
        drugs: s.drugs.map((d) =>
          d.drug === drug
            ? { ...d, call: to, override: { to, reason, by: who, at: new Date().toISOString().slice(0, 16) } }
            : d,
        ),
        audit: [
          ...s.audit,
          {
            at: new Date().toISOString().slice(0, 16),
            who,
            action: `Override · ${drug} → ${to.toLowerCase()}`,
            detail: reason,
          },
        ],
      })),
    [update],
  );

  const reset = useCallback(() => {
    save(seed.specimens as unknown as Specimen[]);
    setRows(seed.specimens as unknown as Specimen[]);
    emit();
  }, []);

  return { rows, ready, release, override, reset };
}

export function useThresholds() {
  const [t, setT] = useState<Thresholds>(DEFAULT_THRESHOLDS);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY_T);
      if (raw) setT(JSON.parse(raw));
    } catch {
      /* fall back to defaults */
    }
  }, []);
  const put = useCallback((next: Thresholds) => {
    setT(next);
    try {
      window.localStorage.setItem(KEY_T, JSON.stringify(next));
    } catch {
      /* non-persistent session */
    }
  }, []);
  return [t, put] as const;
}

/** The signed-in reviewer. A real deployment takes this from the lab's identity provider. */
export const CURRENT_USER = "Dr. A. Haidary";

export type { Seed };
