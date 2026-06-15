"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type HealthTile = {
  tile: string;
  status: "pass" | "warn" | "fail";
  reason: string;
  details?: GenericMap;
};

type HealthDashboard = {
  banner: "pass" | "warn" | "fail";
  p0_breached: boolean;
  p0_failures: string[];
  tiles: HealthTile[];
};

const TILE_LABELS: Record<string, string> = {
  embedding_dimension: "Embedding dimension",
  embedding_registry_metadata: "Embedding registry",
  active_profiles_promoted: "Active profiles",
  migration_ledger: "Migration ledger",
  vector_serving: "Vector serving",
  reranker_warmup: "Reranker warm-up",
  semantic_cache: "Semantic cache",
  eval_gate: "Eval gate",
};

const STATUS_COLORS: Record<string, { bg: string; fg: string; dot: string }> = {
  pass: { bg: "var(--color-background-success)", fg: "var(--color-text-success)", dot: "var(--color-text-success)" },
  warn: { bg: "var(--color-background-warning)", fg: "var(--color-text-warning)", dot: "var(--color-text-warning)" },
  fail: { bg: "var(--color-background-danger)", fg: "var(--color-text-danger)", dot: "var(--color-text-danger)" },
};

export function AdminHealthPanel() {
  const [data, setData] = useState<HealthDashboard | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      setData(await browserFetch<HealthDashboard>("/admin/health/dashboard"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load health dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const bannerStatus = data?.banner ?? "pass";
  const bannerColor = STATUS_COLORS[bannerStatus];
  const bannerText =
    bannerStatus === "fail"
      ? data?.p0_breached
        ? `P0 coherence breached: ${data.p0_failures.join(", ")}`
        : "One or more health checks are failing."
      : bannerStatus === "warn"
        ? "Operational checks need attention; core invariants are healthy."
        : "All coherence invariants and operational checks are healthy.";

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2>System Health &amp; Coherence</h2>
          <p>One answer to &ldquo;is this system coherent right now?&rdquo; — AR2 invariants plus warm-up, cache, and the eval gate.</p>
        </div>
        <button type="button" className="button button-secondary" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}

      <div
        role="status"
        style={{
          background: bannerColor.bg,
          color: bannerColor.fg,
          borderRadius: "var(--border-radius-md)",
          padding: "12px 16px",
          fontWeight: 500,
        }}
      >
        {bannerStatus === "pass" ? "✓ " : "⚠ "}
        {bannerText}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px" }}>
        {(data?.tiles ?? []).map((tile) => {
          const color = STATUS_COLORS[tile.status];
          return (
            <article
              key={tile.tile}
              style={{
                background: "var(--color-background-primary)",
                border: "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-lg)",
                padding: "1rem 1.25rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: color.dot, flexShrink: 0 }} />
                <strong style={{ fontSize: 14 }}>{TILE_LABELS[tile.tile] ?? tile.tile}</strong>
                <span style={{ marginLeft: "auto", fontSize: 12, color: color.fg, textTransform: "uppercase" }}>{tile.status}</span>
              </div>
              <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.5 }}>{tile.reason}</p>
            </article>
          );
        })}
      </div>

      <SystemPosture />
    </section>
  );
}

type PostureItem = { label: string; value: unknown; editable_via: string; requires_restart: boolean };

const POSTURE_GROUPS: { key: string; label: string; help: string }[] = [
  { key: "serving", label: "Vector serving", help: "Whether semantic (vector) search can run. If the active embedding model's dimension differs from the index, search falls back to keyword-only until a reindex completes." },
  { key: "cache", label: "Semantic cache", help: "Whether answers are reused from the governed cache. It is OFF until an admin creates and activates a cache policy — until then every question is answered fresh." },
  { key: "retrieval_defaults", label: "Retrieval defaults", help: "The live retrieval profile's defaults — search mode, query transformation, multi-query fan-out, and reranking. Several are off by default and tuned per profile." },
  { key: "eval_enforcement", label: "Eval enforcement", help: "Whether promoting a tuning candidate requires a passing eval run. 'require' blocks promotion without evidence; 'warn' allows it but records a warning." },
  { key: "workers", label: "Workers", help: "This build is single-process: the ingestion queue, rate limits, and model singletons live in one process. Running multiple web workers is refused unless explicitly allowed." },
  { key: "rate_limits", label: "Rate limits", help: "Per-minute request caps protecting the backend. Changed via environment variables and a restart." },
  { key: "cost_governance", label: "Cost governance", help: "The per-request USD alert threshold and the model price table used to estimate generation cost. Both are editable from the Cost / Providers console." },
];

function InfoDot({ help }: { help: string }) {
  return (
    <span
      title={help}
      aria-label={help}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 15,
        height: 15,
        borderRadius: "50%",
        border: "1px solid var(--color-border-secondary)",
        color: "var(--color-text-secondary)",
        fontSize: 10,
        fontWeight: 600,
        cursor: "help",
        flexShrink: 0,
      }}
    >
      i
    </span>
  );
}

function editBadge(via: string) {
  const ui = via.startsWith("ui");
  const env = via.startsWith("env");
  const bg = ui ? "var(--color-background-info)" : env ? "var(--color-background-secondary)" : "var(--color-background-secondary)";
  const fg = ui ? "var(--color-text-info)" : "var(--color-text-secondary)";
  return <span style={{ fontSize: 11, background: bg, color: fg, borderRadius: "var(--border-radius-md)", padding: "1px 8px", fontFamily: "var(--font-mono)" }}>{via}</span>;
}

function SystemPosture() {
  const [posture, setPosture] = useState<Record<string, GenericMap> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    browserFetch<Record<string, GenericMap>>("/admin/system/posture")
      .then(setPosture)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load system posture."));
  }, []);

  if (error) return <p style={{ color: "var(--color-text-danger)", fontSize: 13 }}>{error}</p>;
  if (!posture) return null;

  return (
    <div style={{ borderTop: "0.5px solid var(--color-border-tertiary)", paddingTop: "1rem" }}>
      <h3 style={{ fontSize: 16, margin: "0 0 4px" }}>System Posture</h3>
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 12px" }}>
        Everything an operator must know without reading the environment or the database. Items marked <code>env:…</code> are changed by editing configuration and restarting; <code>policy</code>/<code>profile</code> are changed in this console.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {POSTURE_GROUPS.map((group) => {
          const section = posture[group.key] as GenericMap | undefined;
          const items = (section?.items as PostureItem[] | undefined) ?? [];
          const headline = section?.headline as string | undefined;
          return (
            <div key={group.key}>
              <p style={{ fontSize: 13, fontWeight: 500, margin: "0 0 4px", display: "flex", alignItems: "center", gap: 6 }}>
                {group.label}
                <InfoDot help={group.help} />
              </p>
              {headline ? <p style={{ fontSize: 12.5, color: "var(--color-text-secondary)", margin: "0 0 6px" }}>{headline}</p> : null}
              <table style={{ width: "100%", fontSize: 12.5, borderCollapse: "collapse" }}>
                <tbody>
                  {items.map((item, i) => (
                    <tr key={i} style={{ borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                      <td style={{ padding: "5px 8px", color: "var(--color-text-secondary)", width: "40%" }}>{item.label}</td>
                      <td style={{ padding: "5px 8px" }}>{item.value === null || item.value === undefined ? "—" : String(item.value)}</td>
                      <td style={{ padding: "5px 8px", textAlign: "right" }}>
                        {editBadge(item.editable_via)}
                        {item.requires_restart ? <span style={{ fontSize: 11, color: "var(--color-text-warning)", marginLeft: 6 }}>restart</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </div>
  );
}
