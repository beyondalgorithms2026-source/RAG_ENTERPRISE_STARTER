"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import { TextInput } from "@/components/ui/TextInput";
import { NumberInput } from "@/components/ui/NumberInput";

type GenericMap = Record<string, unknown>;

type CostSummary = {
  group_by: string;
  buckets: GenericMap[];
  totals: GenericMap;
  governance: GenericMap;
};

type RuntimeSetting = { effective: unknown; override: unknown; source: string };
type RuntimeSettings = { settings: Record<string, RuntimeSetting> };
type PriceRow = { model: string; input: number; output: number };

const GROUPINGS = [
  { key: "retrieval_mode", label: "By mode (deep research vs fast)" },
  { key: "model", label: "By model" },
  { key: "provider", label: "By provider" },
];

function usd(value: unknown) {
  const n = Number(value ?? 0);
  return `$${n.toFixed(4)}`;
}

function humanize(value: string) {
  return String(value || "").replace(/_/g, " ");
}

export function AdminCostPanel() {
  const [groupBy, setGroupBy] = useState("retrieval_mode");
  const [data, setData] = useState<CostSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [runtime, setRuntime] = useState<RuntimeSettings | null>(null);
  const [budget, setBudget] = useState(0);
  const [prices, setPrices] = useState<PriceRow[]>([]);
  const [approvalActor, setApprovalActor] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function refresh(group: string) {
    setLoading(true);
    try {
      const [summary, settings] = await Promise.all([
        browserFetch<CostSummary>(`/admin/cost/summary?group_by=${group}`),
        browserFetch<RuntimeSettings>("/admin/runtime-settings"),
      ]);
      setData(summary);
      setRuntime(settings);
      const alert = settings.settings.llm_cost_alert_usd;
      setBudget(Number(alert.override ?? alert.effective ?? 0));
      const table = (settings.settings.llm_price_table.override ?? settings.settings.llm_price_table.effective ?? {}) as Record<string, number[]>;
      setPrices(Object.entries(table).map(([model, values]) => ({ model, input: Number(values[0] || 0), output: Number(values[1] || 0) })));
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

  function approvalHeaders() {
    return approvalActor.trim() ? { "X-Approval-Actor": approvalActor.trim() } : undefined;
  }

  async function saveGovernance() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const priceTable = Object.fromEntries(prices.filter((row) => row.model.trim()).map((row) => [row.model.trim(), [row.input, row.output]]));
      await browserFetch("/admin/runtime-settings", {
        method: "PATCH",
        headers: approvalHeaders(),
        json: { key: "llm_cost_alert_usd", value: budget },
      });
      await browserFetch("/admin/runtime-settings", {
        method: "PATCH",
        headers: approvalHeaders(),
        json: { key: "llm_price_table", value: priceTable },
      });
      setMessage("Cost governance saved.");
      await refresh(groupBy);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save cost governance.");
    } finally {
      setSaving(false);
    }
  }

  async function resetGovernance() {
    setSaving(true);
    setError("");
    try {
      for (const key of ["llm_cost_alert_usd", "llm_price_table"]) {
        await browserFetch("/admin/runtime-settings", {
          method: "PATCH",
          headers: approvalHeaders(),
          json: { key, value: null },
        });
      }
      setMessage("Runtime overrides cleared.");
      await refresh(groupBy);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset cost governance.");
    } finally {
      setSaving(false);
    }
  }

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
      {message ? <p style={{ color: "var(--color-text-success)" }}>{message}</p> : null}
      {loading ? <p style={{ color: "var(--color-text-secondary)" }}>Loading…</p> : null}

      {data ? (
        <>
          <div style={{ border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-md)", padding: "1rem", display: "grid", gap: "12px" }}>
            <div className="section-head">
              <h3>Runtime budget and model prices</h3>
              <p>Prices are USD per 1K input/output tokens. Runtime values override environment settings without a restart.</p>
            </div>
            <label style={{ display: "grid", gap: 4, maxWidth: 280 }}>
              <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>Per-request cost alert (USD)</span>
              <NumberInput min={0} step="0.000001" value={budget} onChange={(event) => setBudget(Number(event.target.value))} />
              <small>Effective source: {runtime?.settings.llm_cost_alert_usd.source || "unknown"}</small>
            </label>
            <div style={{ display: "grid", gap: 8 }}>
              {prices.map((row, index) => (
                <div key={`${row.model}-${index}`} style={{ display: "grid", gridTemplateColumns: "minmax(160px, 1fr) 140px 140px auto", gap: 8 }}>
                  <TextInput aria-label="Model" placeholder="model name" value={row.model} onChange={(event) => setPrices((current) => current.map((item, i) => i === index ? { ...item, model: event.target.value } : item))} />
                  <TextInput aria-label="Input USD per 1K" type="number" min={0} step="0.000001" value={row.input} onChange={(event) => setPrices((current) => current.map((item, i) => i === index ? { ...item, input: Number(event.target.value) } : item))} />
                  <TextInput aria-label="Output USD per 1K" type="number" min={0} step="0.000001" value={row.output} onChange={(event) => setPrices((current) => current.map((item, i) => i === index ? { ...item, output: Number(event.target.value) } : item))} />
                  <button type="button" className="button button-secondary" onClick={() => setPrices((current) => current.filter((_, i) => i !== index))}>Remove</button>
                </div>
              ))}
              <small>Effective price source: {runtime?.settings.llm_price_table.source || "unknown"}</small>
              <button type="button" className="button button-secondary" style={{ width: "fit-content" }} onClick={() => setPrices((current) => [...current, { model: "", input: 0, output: 0 }])}>Add model price</button>
            </div>
            <label style={{ display: "grid", gap: 4, maxWidth: 320 }}>
              <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>Approval actor (required in governed production)</span>
              <TextInput value={approvalActor} onChange={(event) => setApprovalActor(event.target.value)} placeholder="Separate approver user ID" />
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="button button-primary" disabled={saving} onClick={saveGovernance}>{saving ? "Saving…" : "Save governance"}</button>
              <button type="button" className="button button-secondary" disabled={saving} onClick={resetGovernance}>Reset runtime overrides</button>
            </div>
          </div>

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

          <div className="admin-table-scroll">
            <table className="admin-data-table">
              <thead>
                <tr>
                  <th>{humanize(data.group_by)}</th>
                  <th>Requests</th>
                  <th>Tokens</th>
                  <th>Total cost</th>
                  <th>Avg latency</th>
                  <th>Over budget</th>
                </tr>
              </thead>
              <tbody>
                {data.buckets.map((b) => (
                  <tr key={String(b.bucket)}>
                    <td>
                      {humanize(String(b.bucket))}
                      {b.any_estimated ? <span style={{ color: "var(--color-text-warning)", marginLeft: 6, fontSize: 11 }}>est.</span> : null}
                    </td>
                    <td>{String(b.request_count)}</td>
                    <td>{String(b.total_tokens ?? 0)}</td>
                    <td>{usd(b.total_cost_usd)}</td>
                    <td>{b.avg_latency_ms != null ? `${Number(b.avg_latency_ms).toFixed(0)} ms` : "—"}</td>
                    <td>{String(b.over_budget_count ?? 0)}</td>
                  </tr>
                ))}
                {data.buckets.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ color: "var(--color-text-secondary)" }}>No generation usage recorded yet.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
