"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type Dashboard = { banner: "pass" | "warn" | "fail"; p0_breached: boolean; p0_failures: string[] };

const STYLES = {
  fail: { bg: "var(--color-background-danger)", fg: "var(--color-text-danger)", icon: "⚠" },
  warn: { bg: "var(--color-background-warning)", fg: "var(--color-text-warning)", icon: "⚠" },
};

export function AdminHealthBanner() {
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    let active = true;
    browserFetch<Dashboard>("/admin/health/dashboard")
      .then((d) => active && setData(d))
      .catch(() => active && setData(null));
    return () => {
      active = false;
    };
  }, []);

  // Only render when something needs attention — a healthy system shows nothing.
  if (!data || data.banner === "pass") return null;
  const style = STYLES[data.banner];
  const message = data.p0_breached
    ? `Coherence breached (P0): ${data.p0_failures.join(", ")}. The system may be serving incorrectly.`
    : "Operational checks need attention; core invariants are healthy.";

  return (
    <a
      href="/console/admin/health"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        background: style.bg,
        color: style.fg,
        textDecoration: "none",
        padding: "8px 16px",
        fontSize: "13px",
        fontWeight: 500,
        borderRadius: "var(--border-radius-md)",
        margin: "0 0 12px",
      }}
    >
      <span aria-hidden="true">{style.icon}</span>
      <span>{message}</span>
      <span style={{ marginLeft: "auto", opacity: 0.8 }}>View health →</span>
    </a>
  );
}
