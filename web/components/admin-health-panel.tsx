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
    </section>
  );
}
