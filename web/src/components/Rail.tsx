"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useSpecimens, CURRENT_USER } from "@/lib/store";

function Icon({ d }: { d: string }) {
  return (
    <svg
      className="size-[15px] shrink-0 opacity-80"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}

const PATHS = {
  worklist: "M4 6h16M4 12h16M4 18h10",
  plus: "M12 5v14M5 12h14",
  check: "M9 11l3 3L20 5M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2",
  pulse: "M3 12h4l3 8 4-16 3 8h4",
  chart: "M4 19V9M10 19V5M16 19v-7M22 19H2",
  shield: "M12 2 4 6v6c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10V6z",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.2A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H1a2 2 0 1 1 0-4h.2A1.7 1.7 0 0 0 2.6 9a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.4 1Z",
};

export function Rail() {
  const path = usePathname();
  const { rows } = useSpecimens();

  const review = rows.filter((s) => s.status === "review").length;
  const awaitingAst = rows.filter((s) => s.status === "released").length;

  const groups: { title: string; items: { href: string; label: string; icon: string; count?: number }[] }[] = [
    {
      title: "Workflow",
      items: [
        { href: "/", label: "Worklist", icon: PATHS.worklist, count: rows.length },
        { href: "/new", label: "New analysis", icon: PATHS.plus },
        { href: "/review", label: "Awaiting review", icon: PATHS.check, count: review },
      ],
    },
    {
      title: "Evidence",
      items: [
        { href: "/history", label: "History", icon: PATHS.clock },
        { href: "/reconciliation", label: "Reconciliation", icon: PATHS.pulse, count: awaitingAst },
        { href: "/surveillance", label: "Surveillance", icon: PATHS.chart },
      ],
    },
    {
      title: "System",
      items: [
        { href: "/validation", label: "Model & validation", icon: PATHS.shield },
        { href: "/settings", label: "Settings", icon: PATHS.gear },
      ],
    },
  ];

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-[230px] flex-col border-r border-line bg-surface">
      <Link href="/" className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <svg
          className="size-5 text-accent"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          strokeLinejoin="round"
        >
          <path d="M12 2.5 20.5 7v10L12 21.5 3.5 17V7z" />
          <path d="M12 8.2 16 10.4v4.4L12 17l-4-2.2v-4.4z" />
        </svg>
        <span className="text-[14.5px] font-semibold tracking-tight">Genome Firewall</span>
      </Link>

      <nav className="flex-1 overflow-y-auto pb-4">
        {groups.map((g) => (
          <div key={g.title}>
            <div className="px-5 pt-4 pb-1.5 text-[9.5px] font-semibold tracking-[0.12em] text-faint uppercase">
              {g.title}
            </div>
            {g.items.map((it) => {
              const active = it.href === "/" ? path === "/" : path.startsWith(it.href);
              return (
                <Link
                  key={it.href}
                  href={it.href}
                  aria-current={active ? "page" : undefined}
                  className={`mx-2.5 flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] transition-colors duration-150 ${
                    active
                      ? "bg-accent font-medium text-white"
                      : "text-muted hover:bg-surface-2 hover:text-ink"
                  }`}
                >
                  <Icon d={it.icon} />
                  <span className="truncate">{it.label}</span>
                  {it.count !== undefined && it.count > 0 && (
                    <span
                      className={`tnum ml-auto rounded-full px-1.5 py-px font-mono text-[10.5px] ${
                        active ? "bg-white/25 text-white" : "bg-surface-2 text-faint"
                      }`}
                    >
                      {it.count}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="border-t border-line px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">
            JH
          </div>
          <div className="min-w-0">
            <div className="truncate text-[12.5px] font-medium">{CURRENT_USER}</div>
            <div className="text-[11px] text-faint">Consultant microbiologist</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function PageHeader({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start gap-6">
      <div className="min-w-0">
        <h1 className="text-[25px] leading-tight font-semibold tracking-[-0.022em]">{title}</h1>
        {sub && <p className="mt-1.5 max-w-[68ch] text-[13px] text-muted">{sub}</p>}
      </div>
      {actions && <div className="ml-auto flex shrink-0 gap-2.5">{actions}</div>}
    </div>
  );
}
