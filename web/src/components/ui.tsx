import type { ReactNode } from "react";
import type { Call } from "@/lib/types";

/* ── status chips ───────────────────────────────────────────────────────────
   Colour is never the only signal. Every chip carries a glyph and a word, so a
   colour-blind reader loses nothing. This is a patient-safety requirement, not
   a stylistic one.                                                          */

const CALL_STYLE: Record<Call, { bg: string; fg: string; ring: string; glyph: string; word: string }> = {
  RESISTANT: {
    bg: "bg-resistant-soft",
    fg: "text-resistant",
    ring: "ring-resistant-line",
    glyph: "R",
    word: "Resistant",
  },
  SUSCEPTIBLE: {
    bg: "bg-susceptible-soft",
    fg: "text-susceptible",
    ring: "ring-susceptible-line",
    glyph: "S",
    word: "Susceptible",
  },
  INDETERMINATE: {
    bg: "bg-deferred-soft",
    fg: "text-deferred",
    ring: "ring-deferred-line",
    glyph: "?",
    word: "Deferred",
  },
};

export function CallChip({ call, size = "md" }: { call: Call; size?: "sm" | "md" }) {
  const s = CALL_STYLE[call];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ring-1 font-semibold ${s.bg} ${s.fg} ${s.ring} ${
        size === "sm" ? "px-2 py-0.5 text-[10.5px]" : "px-2.5 py-1 text-[11px]"
      }`}
    >
      <span className="font-mono font-bold" aria-hidden>
        {s.glyph}
      </span>
      {s.word}
    </span>
  );
}

export function Chip({
  children,
  tone = "neutral",
  mono = false,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "resistant" | "susceptible" | "deferred";
  mono?: boolean;
}) {
  const tones = {
    neutral: "bg-surface-2 text-muted ring-line",
    accent: "bg-accent-soft text-accent ring-accent-line",
    resistant: "bg-resistant-soft text-resistant ring-resistant-line",
    susceptible: "bg-susceptible-soft text-susceptible ring-susceptible-line",
    deferred: "bg-deferred-soft text-deferred ring-deferred-line",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${
        tones[tone]
      } ${mono ? "font-mono text-[10.5px]" : ""}`}
    >
      {children}
    </span>
  );
}

/* ── confidence meter ──────────────────────────────────────────────────────── */

export function Meter({ value, call }: { value: number; call: Call }) {
  const colour =
    call === "RESISTANT"
      ? "bg-resistant"
      : call === "SUSCEPTIBLE"
        ? "bg-susceptible"
        : "bg-deferred";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
      <div
        className={`animate-grow h-full rounded-full ${colour}`}
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

/* ── layout primitives ─────────────────────────────────────────────────────── */

export function Card({
  children,
  className = "",
  pad = true,
}: {
  children: ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return <div className={`card ${pad ? "p-5" : ""} ${className}`}>{children}</div>;
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="mb-3 text-[11.5px] font-semibold text-faint">{children}</div>;
}

export function Stat({
  value,
  label,
  note,
  tone,
}: {
  value: ReactNode;
  label: string;
  note?: string;
  tone?: "accent" | "resistant" | "deferred";
}) {
  const c =
    tone === "resistant" ? "text-resistant" : tone === "deferred" ? "text-deferred" : "text-ink";
  return (
    <Card>
      <div className={`tnum font-mono text-[26px] leading-none font-semibold ${c}`}>{value}</div>
      <div className="mt-2 text-[12px] leading-snug text-muted">{label}</div>
      {note && <div className="tnum mt-1.5 font-mono text-[11px] text-faint">{note}</div>}
    </Card>
  );
}

export function Button({
  children,
  variant = "primary",
  onClick,
  type = "button",
  disabled,
  className = "",
}: {
  children: ReactNode;
  variant?: "primary" | "ghost" | "danger";
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
}) {
  const v = {
    primary: "bg-accent text-white hover:bg-accent-hover shadow-sm",
    ghost: "text-muted ring-1 ring-line-strong hover:bg-surface-2 hover:text-ink",
    danger: "text-resistant ring-1 ring-resistant-line hover:bg-resistant-soft",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-[10px] px-3.5 py-2 text-[13px] font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-45 ${v} ${className}`}
    >
      {children}
    </button>
  );
}

/* ── alert ──────────────────────────────────────────────────────────────────── */

export function Alert({
  tone = "danger",
  title,
  children,
}: {
  tone?: "danger" | "warn" | "accent";
  title?: string;
  children: ReactNode;
}) {
  const t = {
    danger: "bg-resistant-soft ring-resistant-line text-resistant",
    warn: "bg-deferred-soft ring-deferred-line text-deferred",
    accent: "bg-accent-soft ring-accent-line text-accent",
  }[tone];
  return (
    <div className={`rounded-[10px] p-3.5 ring-1 ${t}`}>
      <div className="flex gap-2.5">
        <WarnIcon className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0">
          {title && <div className="mb-1 text-[11px] font-semibold tracking-wide uppercase">{title}</div>}
          <div className="text-[12.5px] leading-relaxed text-ink/80">{children}</div>
        </div>
      </div>
    </div>
  );
}

export function WarnIcon({ className = "size-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </svg>
  );
}

export function Dot({ urgent }: { urgent: boolean }) {
  return (
    <span
      className={`inline-block size-[7px] shrink-0 rounded-full ${
        urgent ? "bg-resistant ring-3 ring-resistant/20" : "bg-faint"
      }`}
      title={urgent ? "Urgent" : "Routine"}
    />
  );
}

/** Canonical tokens are stored lowercase for matching; render them the way a
 *  microbiologist writes them. */
const TOKEN_CASE: Record<string, string> = {
  blakpc: "blaKPC", blandm: "blaNDM", blavim: "blaVIM", blaimp: "blaIMP",
  "blaoxa-48": "blaOXA-48", blaoxa: "blaOXA", "blactx-m": "blaCTX-M",
  blatem: "blaTEM", blashv: "blaSHV", blages: "blaGES", blaampc: "blaAmpC",
  sul: "sul", dfr: "dfr", tet: "tet", mph: "mph", cata: "catA", catb: "catB",
  fosa: "fosA", mcr: "mcr", qnra: "qnrA", qnrb: "qnrB", qnrs: "qnrS",
  oqxab: "oqxAB", aada: "aadA", arma: "armA", rmt: "rmt", emrab: "emrAB",
  acrab: "acrAB", mrx: "mrx", qace: "qacE",
};

export function prettyToken(t: string): string {
  if (t.startsWith("POINT:")) return `${t.slice(6)} mutation`;
  if (t.startsWith("TRUNC:")) return `${t.slice(6)} loss`;
  if (TOKEN_CASE[t]) return TOKEN_CASE[t];
  // aac(6') / aph(3'') style — uppercase the enzyme prefix
  return t.replace(/^(aac|aph|ant)\(/, (m) => m.toUpperCase());
}

export function relTime(iso: string) {
  const then = new Date(iso).getTime();
  const now = new Date("2026-07-19T09:00").getTime();
  const h = Math.round((now - then) / 3.6e6);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
