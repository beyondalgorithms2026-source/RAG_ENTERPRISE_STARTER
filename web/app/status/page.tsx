import { SiteMetaPage } from "@/components/site-meta-page";
import { API_BASE_URL } from "@/lib/api-base";

type LiveMetrics = {
  generated_at: string;
  sample_size: number;
  minimum_samples: number;
  readiness: "ready" | "not_ready" | "unavailable";
  public_source_count: number;
  demo_source_count: number;
  expected_demo_source_count: number;
  status: "pass" | "warn" | "breach" | "insufficient_data";
  metrics: {
    mean_latency_ms: number | null;
    p50_latency_ms: number | null;
    p95_latency_ms: number | null;
    max_latency_ms: number | null;
    average_cost_usd_per_query: number | null;
    recovery_rate: number | null;
  };
};

async function getLiveMetrics(): Promise<LiveMetrics | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/metrics/live`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return null;
    return (await response.json()) as LiveMetrics;
  } catch {
    return null;
  }
}

function runtimeSummary(metrics: LiveMetrics | null): string {
  if (!metrics || metrics.readiness === "unavailable") {
    return "The backend is sleeping, unreachable, or not ready. No live metric is inferred from that state.";
  }
  if (metrics.status === "insufficient_data") {
    return `Backend readiness is ${metrics.readiness}. The rolling 24-hour window has ${metrics.sample_size} of ${metrics.minimum_samples} required samples, so no performance status is claimed.`;
  }
  const values = metrics.metrics;
  return `Rolling 24-hour status: ${metrics.status}. Sample size ${metrics.sample_size}; mean ${values.mean_latency_ms?.toFixed(0)} ms; P50 ${values.p50_latency_ms?.toFixed(0)} ms; P95 ${values.p95_latency_ms?.toFixed(0)} ms; average generation cost $${values.average_cost_usd_per_query?.toFixed(4)} per query; recovery rate ${((values.recovery_rate || 0) * 100).toFixed(1)}%. Generated ${metrics.generated_at}.`;
}

export default async function StatusPage() {
  const live = await getLiveMetrics();
  const sourceSummary = live
    ? `The deployment reports ${live.demo_source_count} of ${live.expected_demo_source_count} synthetic demo sources, including ${live.public_source_count} public sources. Readiness: ${live.readiness}.`
    : "The source inventory cannot be read while the backend is unavailable; no count is substituted.";

  return (
    <SiteMetaPage
      eyebrow="Measured status"
      title="Approved quality and live runtime"
      description="The approved evaluation snapshot is historical release evidence. Live metrics are a separate rolling operational view and may be unavailable or insufficient."
      sections={[
        {
          heading: "Approved full-stack baseline v1",
          body: "The owner-approved APP → MCP → STARTER → PostgreSQL/pgvector baseline records 25/25 cases, all five required refusals, and the live RT-06 denied/authorized ACL control. The expanded 90-case v2 suite is not an approved claim until ten eligible calibration runs and review are complete.",
        },
        {
          heading: "Live 24-hour runtime",
          body: runtimeSummary(live),
        },
        {
          heading: "Synthetic corpus readiness",
          body: sourceSummary,
        },
        {
          heading: "Disclosure",
          body: "The Northwind Logistics corpus and Operations Manual v3.2 are fictional demonstration content. They contain no real company, employee, customer, or private data. Metrics never expose questions, users, prompts, raw traces, token details, stack traces, or total spend.",
        },
      ]}
    />
  );
}
