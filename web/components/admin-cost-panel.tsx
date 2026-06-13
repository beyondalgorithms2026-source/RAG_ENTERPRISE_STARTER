"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type CostSummary = {
  group_by: string;
  buckets: GenericMap[];
  totals: GenericMap;
};

const GROUPINGS = [
  { key: "retrieval_mode", label: "By mode (deep research vs fast)" },
  { key: "model", label: "By model" },
  { key: "provider", label: "By provider" },
];

function usd(value: unknown) {
  const n = Number(value ?? 0);
  return `$${n.toFixed(4)}`;
}

export function AdminCostPanel() {
  const [groupBy, setGroupBy] = useState("retrieval_mode");
  const [data, setData] = useState<CostSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh(group: string) {
    setLoading(true);
    try {
      setData(await browserFetch<CostSummary>(`/admin/cost/summary?group_by=${group}`));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cost summary.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh(groupBy);
  }, [groupBy]);

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head">
        <h2>Cost &amp; Token Governance</h2>
        <p>Token counts and estimated USD per generation, rolled up so you can compare what deep research costs versus fast mode.</p>
      </div>

      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {GROUPINGS.map((g) => (
          <button
            key={g.key}
            type="button"
            className={`button ${groupBy === g.key ? "button-primary" : "button-secondary"}`}
            onClick={() => setGroupBy(g.key)}
          >
            {g.label}
          </button>
        ))}
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}
      {loading ? <p style={{ color: "var(--color-text-secondary)" }}>Loading…</p> : null}

      {data ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px" }}>
            <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "1rem" }}>
              <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>Total requests</p>
              <p style={{ fontSize: 22, fontWeight: 500, margin: 0 }}>{String(data.totals.request_count ?? 0)}</p>
            </div>
            <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "1rem" }}>
              <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>Total tokens</p>
              <p style={{ fontSize: 22, fontWeight: 500, margin: 0 }}>{String(data.totals.total_tokens ?? 0)}</p>
            </div>
            <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "1rem" }}>
              <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>Total cost</p>
              <p style={{ fontSize: 22, fontWeight: 500, margin: 0 }}>{usd(data.totals.total_cost_usd)}</p>
            </div>
          </div>

          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
                <th style={{ padding: "6px 8px" }}>{data.group_by}</th>
                <th style={{ padding: "6px 8px" }}>Requests</th>
                <th style={{ padding: "6px 8px" }}>Tokens</th>
                <th style={{ padding: "6px 8px" }}>Total cost</th>
                <th style={{ padding: "6px 8px" }}>Avg latency</th>
                <th style={{ padding: "6px 8px" }}>Over budget</th>
              </tr>
            </thead>
            <tbody>
              {data.buckets.map((b) => (
                <tr key={String(b.bucket)} style={{ borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                  <td style={{ padding: "6px 8px" }}>
                    {String(b.bucket)}
                    {b.any_estimated ? <span style={{ color: "var(--color-text-warning)", marginLeft: 6, fontSize: 11 }}>est.</span> : null}
                  </td>
                  <td style={{ padding: "6px 8px" }}>{String(b.request_count)}</td>
                  <td style={{ padding: "6px 8px" }}>{String(b.total_tokens ?? 0)}</td>
                  <td style={{ padding: "6px 8px" }}>{usd(b.total_cost_usd)}</td>
                  <td style={{ padding: "6px 8px" }}>{b.avg_latency_ms != null ? `${Number(b.avg_latency_ms).toFixed(0)} ms` : "—"}</td>
                  <td style={{ padding: "6px 8px" }}>{String(b.over_budget_count ?? 0)}</td>
                </tr>
              ))}
              {data.buckets.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: "12px 8px", color: "var(--color-text-secondary)" }}>
                    No generation usage recorded yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
