"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type ServingState = {
  vector_serving: { serviceable: boolean; reason: string; profile_dimension?: number | null; index_dimension?: number | null };
  latest_swap: SwapRun | null;
};

type SwapRun = {
  id: number;
  target_profile_name: string;
  target_model?: string;
  target_dimension?: number;
  source_dimension?: number | null;
  requires_reindex?: boolean;
  status: string;
  total_chunks: number;
  embedded_chunks: number;
  failed_chunks?: number;
  verification_json?: GenericMap;
  error?: string | null;
  updated_at?: string;
};

type Plan = {
  target_profile_name: string;
  target_model: string;
  target_dimension: number;
  source_dimension: number | null;
  requires_reindex: boolean;
  requires_column_resize: boolean;
  total_chunks: number;
  already_embedded: number;
};

type EmbeddingOption = { name: string; display_name?: string; model?: string };

const TERMINAL = new Set(["completed", "aborted", "failed"]);

export function AdminEmbeddingPanel() {
  const [serving, setServing] = useState<ServingState | null>(null);
  const [options, setOptions] = useState<EmbeddingOption[]>([]);
  const [liveEmbedding, setLiveEmbedding] = useState("");
  const [target, setTarget] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [run, setRun] = useState<SwapRun | null>(null);
  const [history, setHistory] = useState<SwapRun[]>([]);
  const [approvalActor, setApprovalActor] = useState("");
  const [batchLimit, setBatchLimit] = useState(500);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function loadServing() {
    setServing(await browserFetch<ServingState>("/admin/embedding/serving"));
  }
  async function loadHistory() {
    const data = await browserFetch<{ swap_runs: SwapRun[] }>("/admin/embedding/swaps");
    setHistory(data.swap_runs);
  }
  async function loadOptions() {
    const data = await browserFetch<{ approved_options: { embedding: EmbeddingOption[] }; live_configuration: GenericMap }>("/admin/tuning/configurations");
    setOptions(data.approved_options?.embedding ?? []);
    const live = ((data.live_configuration?.selected_profiles as GenericMap) || {}).embedding as string | undefined;
    setLiveEmbedding(live || "");
    if (!target && live) setTarget(live);
  }

  useEffect(() => {
    Promise.all([loadServing(), loadHistory(), loadOptions()]).catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load embedding state."),
    );
  }, []);

  async function act<T>(label: string, fn: () => Promise<T>): Promise<T | null> {
    setBusy(label);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed.`);
      return null;
    } finally {
      setBusy("");
    }
  }

  async function doPlan() {
    const res = await act("plan", () => browserFetch<{ plan: Plan }>("/admin/embedding/swap/plan", { method: "POST", json: { target_profile_name: target } }));
    if (res) {
      setPlan(res.plan);
      setRun(null);
    }
  }

  async function doBegin() {
    const headers = approvalActor ? { "X-Approval-Actor": approvalActor } : undefined;
    const res = await act("begin", () => browserFetch<{ swap_run: SwapRun }>("/admin/embedding/swap/begin", { method: "POST", json: { target_profile_name: target }, headers }));
    if (res) {
      setRun(res.swap_run);
      await loadServing();
      await loadHistory();
    }
  }

  async function doRun() {
    if (!run) return;
    const res = await act("run", () => browserFetch<{ swap_run: SwapRun }>("/admin/embedding/swap/run", { method: "POST", json: { run_id: run.id, batch_limit: batchLimit } }));
    if (res) {
      setRun(res.swap_run);
      await loadServing();
      await loadHistory();
    }
  }

  async function doVerify() {
    if (!run) return;
    const res = await act("verify", () => browserFetch<{ swap_run: SwapRun }>("/admin/embedding/swap/verify", { method: "POST", json: { run_id: run.id } }));
    if (res) {
      setRun(res.swap_run);
      await loadServing();
      await loadHistory();
    }
  }

  async function doAbort() {
    if (!run) return;
    const res = await act("abort", () => browserFetch<{ swap_run: SwapRun }>("/admin/embedding/swap/abort", { method: "POST", json: { run_id: run.id, reason: "operator_abort_from_console" } }));
    if (res) {
      setRun(res.swap_run);
      await loadServing();
      await loadHistory();
    }
  }

  const serviceable = serving?.vector_serving.serviceable ?? true;
  const pct = run && run.total_chunks ? Math.round((run.embedded_chunks / run.total_chunks) * 100) : 0;
  const runActive = run && !TERMINAL.has(run.status);

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head">
        <h2>Embedding &amp; Model Swap</h2>
        <p>Run a managed embedding-model swap end to end — plan, reindex in batches, verify — without touching the CLI or the database.</p>
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}

      {!serviceable ? (
        <div style={{ background: "var(--color-background-warning)", color: "var(--color-text-warning)", borderRadius: "var(--border-radius-md)", padding: "10px 14px", fontSize: 13, fontWeight: 500 }}>
          ⚠ Vector search is serving keyword-only ({serving?.vector_serving.reason}). It resumes when a reindex completes.
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "12px" }}>
        <Stat label="Vector serving" value={serviceable ? "serviceable" : "degraded"} tone={serviceable ? "ok" : "warn"} />
        <Stat label="Profile dim" value={String(serving?.vector_serving.profile_dimension ?? "—")} />
        <Stat label="Index dim" value={String(serving?.vector_serving.index_dimension ?? "—")} />
        <Stat label="Live embedding" value={liveEmbedding || "—"} />
      </div>

      <div style={{ display: "flex", gap: "8px", alignItems: "flex-end", flexWrap: "wrap" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          <span style={{ color: "var(--color-text-secondary)" }}>Target embedding profile</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)} style={{ minWidth: 240 }}>
            {options.map((o) => (
              <option key={o.name} value={o.name}>
                {(o.display_name || o.name) + (o.model ? ` · ${o.model}` : "")}{o.name === liveEmbedding ? " (live)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="button button-secondary" onClick={doPlan} disabled={busy === "plan" || !target}>
          {busy === "plan" ? "Planning…" : "Plan swap"}
        </button>
      </div>

      {plan ? (
        <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "12px 14px", fontSize: 13, lineHeight: 1.7 }}>
          <strong>Plan:</strong> {plan.target_model} · target dim {plan.target_dimension} vs index dim {plan.source_dimension ?? "—"} ·{" "}
          requires reindex: <strong>{String(plan.requires_reindex)}</strong> · column resize: <strong>{String(plan.requires_column_resize)}</strong> ·{" "}
          {plan.already_embedded}/{plan.total_chunks} chunks already embedded.
          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5 }}>
              <span style={{ color: "var(--color-text-secondary)" }}>Approval actor (prod only)</span>
              <input value={approvalActor} onChange={(e) => setApprovalActor(e.target.value)} placeholder="approver user id" />
            </label>
            <button type="button" className="button button-primary" onClick={doBegin} disabled={busy === "begin" || !!runActive}>
              {busy === "begin" ? "Beginning…" : "Begin swap"}
            </button>
          </div>
        </div>
      ) : null}

      {run ? (
        <div style={{ border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong style={{ fontSize: 14 }}>Run #{run.id}</strong>
            <span style={{ fontSize: 12, textTransform: "uppercase", color: TERMINAL.has(run.status) ? (run.status === "completed" ? "var(--color-text-success)" : "var(--color-text-danger)") : "var(--color-text-info)" }}>{run.status}</span>
            <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--color-text-secondary)" }}>{run.embedded_chunks}/{run.total_chunks} chunks</span>
          </div>
          <div style={{ height: 8, background: "var(--color-background-secondary)", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ width: `${pct}%`, height: "100%", background: "var(--color-text-info)" }} />
          </div>
          {run.status === "reindexing" ? (
            <p style={{ fontSize: 12.5, color: "var(--color-text-warning)", margin: 0 }}>Vector search is serving keyword-only until this reindex completes.</p>
          ) : null}
          {run.verification_json && Object.keys(run.verification_json).length ? (
            <p style={{ fontSize: 12.5, color: "var(--color-text-secondary)", margin: 0 }}>Verification: {JSON.stringify(run.verification_json)}</p>
          ) : null}
          {run.error ? <p style={{ fontSize: 12.5, color: "var(--color-text-danger)", margin: 0 }}>{run.error}</p> : null}
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5 }}>
              <span style={{ color: "var(--color-text-secondary)" }}>Batch limit</span>
              <input type="number" min={1} value={batchLimit} onChange={(e) => setBatchLimit(Number(e.target.value))} style={{ width: 120 }} />
            </label>
            <button type="button" className="button button-secondary" onClick={doRun} disabled={busy === "run" || run.status === "verifying" || TERMINAL.has(run.status)}>
              {busy === "run" ? "Running…" : "Run batch"}
            </button>
            <button type="button" className="button button-secondary" onClick={doVerify} disabled={busy === "verify" || run.status !== "verifying"}>
              {busy === "verify" ? "Verifying…" : "Verify"}
            </button>
            <button type="button" className="button button-secondary" onClick={doAbort} disabled={busy === "abort" || TERMINAL.has(run.status)}>
              Abort
            </button>
          </div>
        </div>
      ) : null}

      <div>
        <h3 style={{ fontSize: 15, margin: "0 0 8px" }}>Swap history</h3>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
              <th style={{ padding: "6px 8px" }}>#</th>
              <th style={{ padding: "6px 8px" }}>Target</th>
              <th style={{ padding: "6px 8px" }}>Status</th>
              <th style={{ padding: "6px 8px" }}>Chunks</th>
              <th style={{ padding: "6px 8px" }}>Updated</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id} style={{ borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                <td style={{ padding: "6px 8px" }}>{h.id}</td>
                <td style={{ padding: "6px 8px" }}>{h.target_profile_name}</td>
                <td style={{ padding: "6px 8px" }}>{h.status}</td>
                <td style={{ padding: "6px 8px" }}>{h.embedded_chunks}/{h.total_chunks}</td>
                <td style={{ padding: "6px 8px", color: "var(--color-text-secondary)" }}>{h.updated_at ? String(h.updated_at).slice(0, 19).replace("T", " ") : "—"}</td>
              </tr>
            ))}
            {history.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: "12px 8px", color: "var(--color-text-secondary)" }}>No swaps recorded yet.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  const color = tone === "warn" ? "var(--color-text-warning)" : tone === "ok" ? "var(--color-text-success)" : "var(--color-text-primary)";
  return (
    <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "0.75rem 1rem" }}>
      <p style={{ fontSize: 12.5, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>{label}</p>
      <p style={{ fontSize: 15, fontWeight: 500, margin: 0, color }}>{value}</p>
    </div>
  );
}
