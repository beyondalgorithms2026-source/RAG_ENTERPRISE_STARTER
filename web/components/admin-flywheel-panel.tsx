"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type TrendPoint = {
  run_id: number;
  label: string;
  gate_status: string;
  recall_at_5: number | null;
  mrr: number | null;
  cumulative_pass_rate: number;
};

export function AdminFlywheelPanel() {
  const [clusterId, setClusterId] = useState("");
  const [packName, setPackName] = useState("general");
  const [proposed, setProposed] = useState<GenericMap[]>([]);
  const [quarantine, setQuarantine] = useState<GenericMap | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [overall, setOverall] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function loadTrend() {
    try {
      const data = await browserFetch<{ points: TrendPoint[]; overall_pass_rate: number | null }>("/admin/feedback-eval/trend");
      setTrend(data.points);
      setOverall(data.overall_pass_rate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load trend.");
    }
  }

  useEffect(() => {
    loadTrend();
  }, []);

  async function propose() {
    setBusy("propose");
    setError("");
    try {
      const data = await browserFetch<{ proposed_cases: GenericMap[] }>("/admin/feedback-eval/propose", { method: "POST", json: { cluster_id: Number(clusterId) } });
      setProposed(data.proposed_cases);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Propose failed.");
    } finally {
      setBusy("");
    }
  }

  async function append() {
    setBusy("append");
    setError("");
    try {
      await browserFetch("/admin/feedback-eval/append", { method: "POST", json: { pack_name: packName, cases: proposed } });
      await loadQuarantine();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Append failed.");
    } finally {
      setBusy("");
    }
  }

  async function loadQuarantine() {
    try {
      setQuarantine(await browserFetch<GenericMap>(`/admin/feedback-eval/quarantine?pack_name=${encodeURIComponent(packName)}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quarantine.");
    }
  }

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head">
        <h2>Feedback → Eval Flywheel</h2>
        <p>Turn thumbs-down failure clusters into quarantined eval cases, review them into gating cases, and watch pack pass-rate trend over time.</p>
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}

      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
        <input style={{ width: 140 }} placeholder="Cluster id" value={clusterId} onChange={(e) => setClusterId(e.target.value)} />
        <button type="button" className="button button-secondary" onClick={propose} disabled={busy === "propose" || !clusterId}>
          {busy === "propose" ? "Proposing…" : "Propose cases"}
        </button>
        <input style={{ width: 160 }} placeholder="Pack name" value={packName} onChange={(e) => setPackName(e.target.value)} />
        <button type="button" className="button button-primary" onClick={append} disabled={busy === "append" || proposed.length === 0}>
          {busy === "append" ? "Appending…" : `Append ${proposed.length} (quarantined)`}
        </button>
        <button type="button" className="button button-secondary" onClick={loadQuarantine}>
          Load quarantine
        </button>
      </div>

      {proposed.length ? (
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          {proposed.length} proposed case(s): {proposed.map((c) => String(c.question)).slice(0, 3).join(" · ")}
        </div>
      ) : null}

      {quarantine ? (
        <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "12px 14px", fontSize: 13 }}>
          <strong>{String(quarantine.pack)}</strong>: {JSON.stringify(quarantine.by_review_status)} — {((quarantine.quarantined_feedback_cases as GenericMap[]) || []).length} feedback case(s) awaiting review.
        </div>
      ) : null}

      <div>
        <h3 style={{ fontSize: 15, margin: "0 0 8px" }}>Pack pass-rate trend {overall != null ? `(overall ${(overall * 100).toFixed(0)}%)` : ""}</h3>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
              <th style={{ padding: "6px 8px" }}>Run</th>
              <th style={{ padding: "6px 8px" }}>Label</th>
              <th style={{ padding: "6px 8px" }}>Gate</th>
              <th style={{ padding: "6px 8px" }}>recall@5</th>
              <th style={{ padding: "6px 8px" }}>MRR</th>
              <th style={{ padding: "6px 8px" }}>Cumulative pass</th>
            </tr>
          </thead>
          <tbody>
            {trend.map((p) => (
              <tr key={p.run_id} style={{ borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                <td style={{ padding: "6px 8px" }}>{p.run_id}</td>
                <td style={{ padding: "6px 8px" }}>{p.label}</td>
                <td style={{ padding: "6px 8px", color: p.gate_status === "pass" ? "var(--color-text-success)" : "var(--color-text-danger)" }}>{p.gate_status}</td>
                <td style={{ padding: "6px 8px" }}>{p.recall_at_5 != null ? p.recall_at_5.toFixed(3) : "—"}</td>
                <td style={{ padding: "6px 8px" }}>{p.mrr != null ? p.mrr.toFixed(3) : "—"}</td>
                <td style={{ padding: "6px 8px" }}>{(p.cumulative_pass_rate * 100).toFixed(0)}%</td>
              </tr>
            ))}
            {trend.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "12px 8px", color: "var(--color-text-secondary)" }}>
                  No eval runs recorded yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
