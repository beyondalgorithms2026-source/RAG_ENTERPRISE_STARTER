"use client";

import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type TuningPayload = {
  live_configuration: GenericMap;
  candidate_drafts: GenericMap[];
  approved_options: Record<string, GenericMap[]>;
  profile_types: string[];
};

type TuningHistory = {
  promotion_events: GenericMap[];
  versions: GenericMap[];
};

type TuningOpsPayload = {
  semanticCache: GenericMap;
  queryMining: {
    events: GenericMap[];
    clusters: GenericMap[];
    eval_packs: GenericMap[];
  };
  governance: {
    risk_signals: GenericMap[];
    restrictions: GenericMap[];
  };
};

type CompareRun = {
  label: string;
  status: string;
  answer: string | null;
  citations: GenericMap[];
  citation_count: number;
  used_chunks_count: number;
  latency_ms: number;
  mode: string | null;
  selected_profiles: Record<string, string>;
  generation_summary: GenericMap;
  retrieval_summary: GenericMap;
  rerank_summary: GenericMap;
  warning?: GenericMap;
};

type ComparePayload = {
  live_run: CompareRun;
  candidate_run: CompareRun | null;
  summary: GenericMap;
  warnings: GenericMap[];
  preconditions: GenericMap[];
};

type PreparedCandidate = {
  draft_id: number | null;
  name: string;
  description: string;
  selected_profiles: Record<string, string>;
  retrieval_override_config: Record<string, unknown>;
  tuning_controls: {
    temperature: number;
    topP: number;
    chunkSize: number;
    retrievalK: number;
  };
  prepared_at: string;
  signature: string;
};

const TUNING_PROFILE_TYPES = ["llm", "embedding", "reranker", "retrieval"] as const;

function profileTypeLabel(profileType: string) {
  if (profileType === "llm") {
    return "Inference Model";
  }
  if (profileType === "embedding") {
    return "Embedding Model";
  }
  if (profileType === "reranker") {
    return "Reranking Logic";
  }
  if (profileType === "retrieval") {
    return "Retrieval Profile";
  }
  return profileType;
}

function transformSummaryText(value: unknown) {
  const summary = (value || {}) as Record<string, unknown>;
  const enabled = Boolean(summary.enabled ?? summary.query_transform_enabled);
  if (!enabled) {
    return "Query transform disabled";
  }
  const strategy = Array.isArray(summary.strategy)
    ? summary.strategy.map((item) => String(item)).filter(Boolean)
    : [
        summary.rewrite_enabled ? "rewrite" : "",
        summary.expansion_enabled ? "expansion" : "",
        summary.hyde_enabled ? "hyde" : "",
      ].filter(Boolean);
  const label = strategy.length ? strategy.join(", ") : "configured";
  return `Enabled: ${label}`;
}

function candidateRetrievalSummary(config: Record<string, unknown>, retrievalK: number) {
  const mode = String(config.default_mode || "hybrid")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  const parts = [mode, `K ${retrievalK}`];

  if (!Boolean(config.query_transform_enabled)) {
    return [...parts, "Transform off"].join(" · ");
  }

  const strategies = [
    config.rewrite_enabled ? "Rewrite" : "",
    config.expansion_enabled ? "Expansion" : "",
    config.hyde_enabled ? "HyDE" : "",
  ].filter(Boolean);
  parts.push(strategies.length ? strategies.join(" + ") : "Transform enabled");
  parts.push(`${Number(config.transform_max_variants ?? 3)} variants`);
  parts.push(`${Number(config.transform_timeout_ms ?? 750)} ms`);
  return parts.join(" · ");
}

function formatMetricDelta(value: unknown) {
  if (typeof value !== "number") {
    return "n/a";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
}

function evalEvidenceSummary(evidence: GenericMap | null | undefined) {
  if (!evidence || !Object.keys(evidence).length) {
    return null;
  }
  const warnings = (evidence.warnings || []) as string[];
  const deltas = (evidence.deltas_vs_live_baseline || {}) as GenericMap;
  const parts: string[] = [];
  parts.push(evidence.eval_run_id ? `eval run #${evidence.eval_run_id} · gate ${String(evidence.gate_status || "unknown")}` : "no eval run");
  if (Object.keys(deltas).length) {
    parts.push(`recall@5 Δ ${formatMetricDelta(deltas.recall_at_5)} · MRR Δ ${formatMetricDelta(deltas.mrr)}`);
  }
  if (warnings.length) {
    parts.push(`⚠ ${warnings.join(", ")}`);
  }
  return parts.join(" · ");
}

function formatTimestamp(value: unknown) {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function versionResolvedConfig(version: GenericMap, profileType: string) {
  return ((((version.resolved_config || {}) as GenericMap)[profileType] || {}) as GenericMap);
}

function versionProfileConfig(version: GenericMap, profileType: string) {
  return ((versionResolvedConfig(version, profileType).config || {}) as GenericMap);
}

function versionProfileName(version: GenericMap, profileType: string) {
  return String(versionProfileConfig(version, profileType).display_name || versionResolvedConfig(version, profileType).profile_name || (((version.selected_profiles || {}) as GenericMap)[profileType] || "default"));
}

function versionModelDetail(version: GenericMap, profileType: string) {
  const config = versionProfileConfig(version, profileType);
  if (profileType === "retrieval") {
    return `${String(config.default_mode || "hybrid")} base · ${transformSummaryText(config)}`;
  }
  return String(config.model || config.dimension || versionProfileName(version, profileType));
}

function selectedProfilesSignature(value: unknown) {
  const profiles = (value || {}) as GenericMap;
  return JSON.stringify(
    TUNING_PROFILE_TYPES.reduce<Record<string, string>>((payload, profileType) => {
      payload[profileType] = String(profiles[profileType] || "");
      return payload;
    }, {})
  );
}

function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="admin-empty-state">
      <span className="material-symbols-outlined">inbox</span>
      <strong>{title}</strong>
      <p>{copy}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="tuning-lab-field">
      <span className="muted-copy">{label}</span>
      {children}
    </label>
  );
}

function ParameterLabel({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <div className="tuning-lab-parameter-label">
      <span className="tuning-lab-parameter-label-text">
        {label}
        <span className="tuning-lab-tooltip-anchor" tabIndex={0}>
          <span className="tuning-lab-tooltip-icon">i</span>
          <span className="tuning-lab-tooltip-bubble">{tooltip}</span>
        </span>
      </span>
    </div>
  );
}

function ToggleControl({
  label,
  enabled,
  onToggle,
  disabled = false,
}: {
  label: string;
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={`tuning-lab-visual-toggle tuning-lab-inline-toggle ${enabled ? "is-on" : ""} ${disabled ? "is-disabled" : ""}`}
      onClick={onToggle}
      disabled={disabled}
      aria-pressed={enabled}
    >
      <span>{`${label} ${enabled ? "On" : "Off"}`}</span>
      <i />
    </button>
  );
}

function renderCompareAnswer(run: CompareRun | null, emptyCopy: string) {
  if (!run) {
    return <div className="tuning-lab-compare-empty">{emptyCopy}</div>;
  }
  if (run.status !== "completed") {
    return <div className="tuning-lab-compare-empty">{String(run.warning?.message || emptyCopy)}</div>;
  }
  return run.answer ? (
    <>
      <div className={`tuning-lab-compare-answer ${run.label === "live" ? "tuning-lab-compare-answer-live" : "tuning-lab-compare-answer-candidate"}`}>
        {run.answer}
      </div>
      <div className="tuning-lab-compare-meta">
        <span>Mode: {run.mode || "unknown"}</span>
        <span>Retrieval path: {String(run.retrieval_summary?.retrieval_path || run.mode || "unknown")}</span>
        <span>Rerank: {String(run.rerank_summary?.enabled ? run.rerank_summary?.model || "enabled" : "off")}</span>
      </div>
      {run.citations.length ? (
        <div className="tuning-lab-compare-citations">
          {run.citations.map((citation, index) => (
            <article key={`${citation.citation_id || index}`} className="tuning-lab-compare-citation-card">
              <strong>
                {String(citation.citation_id || `S${index + 1}`)} · {String(citation.file_name || citation.heading || "Source")}
              </strong>
              <span>{String(citation.heading || citation.locator || citation.source_type || "Grounded evidence")}</span>
              <p>{String(citation.snippet || "").slice(0, 220)}</p>
            </article>
          ))}
        </div>
      ) : null}
    </>
  ) : (
    <div className="tuning-lab-compare-empty">{emptyCopy}</div>
  );
}

export function ProfilesAdminPanel() {
  const historySectionRef = useRef<HTMLElement | null>(null);
  const [tuningPayload, setTuningPayload] = useState<TuningPayload>({
    live_configuration: {},
    candidate_drafts: [],
    approved_options: {},
    profile_types: [],
  });
  const [comparePayload, setComparePayload] = useState<ComparePayload | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isComparing, setIsComparing] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [isPromoting, setIsPromoting] = useState(false);
  const [isRollingBack, setIsRollingBack] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evalRun, setEvalRun] = useState<GenericMap | null>(null);
  const [isOpsBusy, setIsOpsBusy] = useState("");
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [tuningHistory, setTuningHistory] = useState<TuningHistory>({ promotion_events: [], versions: [] });
  const [tuningOps, setTuningOps] = useState<TuningOpsPayload>({
    semanticCache: {},
    queryMining: { events: [], clusters: [], eval_packs: [] },
    governance: { risk_signals: [], restrictions: [] },
  });
  const [visualMode, setVisualMode] = useState(true);
  const [preparedCandidate, setPreparedCandidate] = useState<PreparedCandidate | null>(null);
  const [savedDraftSignature, setSavedDraftSignature] = useState("");
  const [selectedHistoryVersion, setSelectedHistoryVersion] = useState<GenericMap | null>(null);
  const [draftName, setDraftName] = useState("Balanced candidate");
  const [draftDescription, setDraftDescription] = useState("Interactive sandbox candidate for side-by-side compare against the live baseline.");
  const [sampleQuery, setSampleQuery] = useState("How does the Q4 liability clause affect subcontracting?");
  const [promotionNote, setPromotionNote] = useState("Validated in sandbox compare.");
  const [selectedProfiles, setSelectedProfiles] = useState<Record<string, string>>({
    llm: "",
    embedding: "",
    reranker: "",
    retrieval: "",
  });
  const [candidateRetrievalConfig, setCandidateRetrievalConfig] = useState<Record<string, unknown>>({});
  const [tuningControls, setTuningControls] = useState({
    temperature: 0.0,
    topP: 1.0,
    chunkSize: 1500,
    retrievalK: 6,
  });

  async function refresh() {
    setIsLoading(true);
    try {
      const tuning = await browserFetch<TuningPayload>("/admin/tuning/configurations");
      const history = await browserFetch<TuningHistory>("/admin/tuning/history");
      const [semanticCache, queryMiningPayload, governance] = await Promise.all([
        browserFetch<GenericMap>("/admin/semantic-cache"),
        browserFetch<GenericMap>("/admin/query-mining"),
        browserFetch<TuningOpsPayload["governance"]>("/admin/governance"),
      ]);
      const queryMining = {
        events: ((queryMiningPayload.events || queryMiningPayload.query_events || []) as GenericMap[]),
        clusters: ((queryMiningPayload.clusters || []) as GenericMap[]),
        eval_packs: ((queryMiningPayload.eval_packs || queryMiningPayload.derived_eval_packs || []) as GenericMap[]),
      };
      setTuningPayload(tuning);
      setTuningHistory(history);
      setTuningOps({ semanticCache, queryMining, governance });
      setError("");
      const liveSelected = (tuning.live_configuration?.selected_profiles || {}) as Record<string, string>;
      const resolved = (tuning.live_configuration?.resolved_config || {}) as Record<string, GenericMap>;
      const llmConfig = ((resolved.llm || {}).config || {}) as GenericMap;
      setSelectedProfiles((current) => {
        const next = { ...current };
        for (const profileType of TUNING_PROFILE_TYPES) {
          next[profileType] = current[profileType] || liveSelected[profileType] || "";
        }
        return next;
      });
      setCandidateRetrievalConfig((current) => {
        if (Object.keys(current).length) {
          return current;
        }
        return { ...((((resolved.retrieval || {}).config || {}) as GenericMap)) };
      });
      setTuningControls({
        temperature: Number(llmConfig.temperature ?? 0.0),
        topP: Number(llmConfig.top_p ?? 1.0),
        chunkSize: 1500,
        retrievalK: 6,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tuning data.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const seededQuestion = window.localStorage.getItem("rag:tuningSeedQuestion");
    const seededLabel = window.localStorage.getItem("rag:tuningSeedLabel");
    if (seededQuestion) {
      setSampleQuery(seededQuestion);
      setDraftName(seededLabel ? `${seededLabel} candidate` : "Feedback-driven candidate");
      window.localStorage.removeItem("rag:tuningSeedQuestion");
      window.localStorage.removeItem("rag:tuningSeedLabel");
    }
  }, []);

  const liveSelected = (tuningPayload.live_configuration?.selected_profiles || {}) as Record<string, string>;
  const liveResolved = (tuningPayload.live_configuration?.resolved_config || {}) as Record<string, GenericMap>;
  const liveRetrievalConfig = (((liveResolved.retrieval || {}).config || {}) as GenericMap);
  const approvedEmbeddingOptions = useMemo(() => (tuningPayload.approved_options.embedding || []) as GenericMap[], [tuningPayload]);
  const approvedLiveEmbeddingName = useMemo(() => {
    const liveEmbeddingName = liveSelected.embedding || "";
    if (approvedEmbeddingOptions.some((option) => String(option.name) === liveEmbeddingName)) {
      return liveEmbeddingName;
    }
    const liveEmbeddingConfig = (((liveResolved.embedding || {}).config || {}) as GenericMap);
    const liveEmbeddingModel = String(liveEmbeddingConfig.model || "");
    const match = approvedEmbeddingOptions.find((option) => String(((option.config || {}) as GenericMap).model || "") === liveEmbeddingModel);
    return String(match?.name || liveEmbeddingName);
  }, [approvedEmbeddingOptions, liveResolved, liveSelected]);
  const effectiveSelectedProfiles = useMemo(() => {
    const merged: Record<string, string> = {};
    for (const profileType of TUNING_PROFILE_TYPES) {
      merged[profileType] = selectedProfiles[profileType] || liveSelected[profileType] || "";
    }
    return merged;
  }, [liveSelected, selectedProfiles]);
  const retrievalOptions = useMemo(() => (tuningPayload.approved_options.retrieval || []) as GenericMap[], [tuningPayload]);
  const selectedRetrievalBaseConfig = useMemo(() => {
    const selected = effectiveSelectedProfiles.retrieval || "";
    const match = retrievalOptions.find((option) => String(option.name) === selected);
    return ((match?.config || {}) as Record<string, unknown>);
  }, [effectiveSelectedProfiles, retrievalOptions]);
  const draftFormSignature = JSON.stringify({
    name: draftName,
    description: draftDescription,
    selectedProfiles: effectiveSelectedProfiles,
    candidateRetrievalConfig,
  });
  const candidateSignature = JSON.stringify({
    draftId: editingDraftId,
    draftFormSignature,
    tuningControls,
  });
  const isPreparedCurrent = preparedCandidate ? preparedCandidate.signature === candidateSignature : false;
  const hasUnsavedDraftChanges = !editingDraftId || savedDraftSignature !== draftFormSignature;
  const selectedOptionLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const profileType of TUNING_PROFILE_TYPES) {
      const selected = effectiveSelectedProfiles[profileType] || "";
      const options = tuningPayload.approved_options[profileType] || [];
      const match = options.find((option) => String(option.name) === selected);
      const displayMatch = profileType === "embedding"
        ? options.find((option) => String(option.name) === approvedLiveEmbeddingName)
        : null;
      labels[profileType] = String(match?.display_name || match?.name || displayMatch?.display_name || displayMatch?.name || selected || "Not selected");
    }
    return labels;
  }, [approvedLiveEmbeddingName, effectiveSelectedProfiles, tuningPayload]);
  const queryTransformEnabled = Boolean(candidateRetrievalConfig.query_transform_enabled);
  const retrievalOverrideChanged = useMemo(() => {
    const keys = new Set([...Object.keys(selectedRetrievalBaseConfig), ...Object.keys(candidateRetrievalConfig)]);
    return Array.from(keys).some((key) => selectedRetrievalBaseConfig[key] !== candidateRetrievalConfig[key]);
  }, [selectedRetrievalBaseConfig, candidateRetrievalConfig]);

  const expectedChange = useMemo(() => {
    if (comparePayload?.candidate_run?.status === "completed") {
      const delta = comparePayload.summary?.latency_delta_ms;
      if (typeof delta === "number") {
        return delta <= 0
          ? `Candidate ran ${Math.abs(delta)}ms faster than live on the latest sandbox check.`
          : `Candidate ran ${delta}ms slower than live on the latest sandbox check.`;
      }
    }
    let deltaCount = 0;
    for (const profileType of TUNING_PROFILE_TYPES) {
      if ((effectiveSelectedProfiles[profileType] || "") && effectiveSelectedProfiles[profileType] !== (liveSelected[profileType] || "")) {
        deltaCount += 1;
      }
    }
    if (retrievalOverrideChanged) {
      deltaCount += 1;
    }
    if (deltaCount === 0) {
      return "No governed profile swaps yet; this candidate mirrors the live baseline and only tests answer-time controls.";
    }
    return `${deltaCount} governed profile selections differ from production; use sandbox compare before any later rollout step.`;
  }, [comparePayload, effectiveSelectedProfiles, liveSelected, retrievalOverrideChanged]);

  useEffect(() => {
    if (!selectedProfiles.retrieval && !liveSelected.retrieval) {
      return;
    }
    setCandidateRetrievalConfig({ ...selectedRetrievalBaseConfig });
  }, [selectedProfiles.retrieval, liveSelected.retrieval, selectedRetrievalBaseConfig]);

  function updateRetrievalToggle(key: string, value: boolean) {
    setCandidateRetrievalConfig((current) => ({ ...current, [key]: value }));
  }

  function updateRetrievalNumber(key: string, value: number) {
    setCandidateRetrievalConfig((current) => ({ ...current, [key]: value }));
  }

  function resetDraftForm() {
    setEditingDraftId(null);
    setPreparedCandidate(null);
    setSavedDraftSignature("");
    setDraftName("Balanced candidate");
    setDraftDescription("Interactive sandbox candidate for side-by-side compare against the live baseline.");
    setSelectedProfiles({
      llm: liveSelected.llm || "",
      embedding: liveSelected.embedding || "",
      reranker: liveSelected.reranker || "",
      retrieval: liveSelected.retrieval || "",
    });
    setCandidateRetrievalConfig({ ...((((liveResolved.retrieval || {}).config || {}) as GenericMap)) });
    setComparePayload(null);
    setEvalRun(null);
  }

  function prepareSandboxCandidate() {
    setPreparedCandidate({
      draft_id: editingDraftId,
      name: draftName,
      description: draftDescription,
      selected_profiles: { ...effectiveSelectedProfiles },
      retrieval_override_config: { ...candidateRetrievalConfig },
      tuning_controls: { ...tuningControls },
      prepared_at: new Date().toISOString(),
      signature: candidateSignature,
    });
    setComparePayload(null);
    setError("");
  }

  async function saveDraft() {
    setSavingDraft(true);
    try {
      const payload = {
        name: draftName,
        description: draftDescription,
        selected_profiles: effectiveSelectedProfiles,
        retrieval_override_config: candidateRetrievalConfig,
      };
      if (editingDraftId) {
        const response = await browserFetch<{ draft: GenericMap }>(`/admin/tuning/drafts/${editingDraftId}`, { method: "PATCH", json: payload });
        setEditingDraftId(Number(response.draft.id));
      } else {
        const response = await browserFetch<{ draft: GenericMap }>("/admin/tuning/drafts", { method: "POST", json: payload });
        setEditingDraftId(Number(response.draft.id));
      }
      setSavedDraftSignature(draftFormSignature);
      setEvalRun(null); // draft changed: prior eval evidence is stale
      await refresh();
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save candidate draft.");
    } finally {
      setSavingDraft(false);
    }
  }

  async function runCompare() {
    if (!preparedCandidate) {
      setError("Prepare the sandbox candidate first, then run compare.");
      return;
    }
    if (!isPreparedCurrent) {
      setError("Sandbox inputs changed after preparation. Prepare Candidate again to refresh the candidate snapshot before compare.");
      return;
    }
    setIsComparing(true);
    try {
      const compare = await browserFetch<ComparePayload>("/admin/tuning/compare", {
        method: "POST",
        json: {
          question: sampleQuery,
          draft_id: preparedCandidate.draft_id,
          selected_profiles: preparedCandidate.selected_profiles,
          retrieval_override_config: preparedCandidate.retrieval_override_config,
          temperature: preparedCandidate.tuning_controls.temperature,
          top_p: preparedCandidate.tuning_controls.topP,
          chunk_size_cap_chars: preparedCandidate.tuning_controls.chunkSize,
          k_retrieval_count: preparedCandidate.tuning_controls.retrievalK,
        },
      });
      setComparePayload(compare);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sandbox compare failed.");
    } finally {
      setIsComparing(false);
    }
  }

  async function runEvalPack() {
    if (!editingDraftId) {
      setError("Save the candidate as a draft before running the eval pack.");
      return;
    }
    if (hasUnsavedDraftChanges) {
      setError("Update the draft first so the eval run evaluates the current candidate.");
      return;
    }
    setIsEvaluating(true);
    try {
      const response = await browserFetch<{ eval_run: GenericMap }>("/admin/tuning/eval-runs", {
        method: "POST",
        json: { draft_id: editingDraftId },
      });
      setEvalRun(response.eval_run);
      setError("");
    } catch (err) {
      setEvalRun(null);
      setError(err instanceof Error ? err.message : "Eval pack run failed.");
    } finally {
      setIsEvaluating(false);
    }
  }

  async function promoteCandidate() {
    if (!editingDraftId) {
      setError("Save the candidate as a draft before promotion.");
      return;
    }
    setIsPromoting(true);
    try {
      await browserFetch("/admin/tuning/promote", {
        method: "POST",
        json: {
          draft_id: editingDraftId,
          promotion_note: promotionNote,
          eval_run_id: evalRun && Number(evalRun.draft_id) === editingDraftId ? Number(evalRun.id) : null,
        },
      });
      await refresh();
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promotion failed.");
    } finally {
      setIsPromoting(false);
    }
  }

  async function rollbackVersion(versionLabel: string) {
    setIsRollingBack(true);
    try {
      await browserFetch("/admin/tuning/rollback", {
        method: "POST",
        json: {
          version_label: versionLabel,
          reason: "Operator rollback from tuning history.",
        },
      });
      await refresh();
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed.");
    } finally {
      setIsRollingBack(false);
    }
  }

  function scrollToVersionHistory() {
    historySectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    const liveVersion = tuningHistory.versions.find((version) => String(version.version_label) === "live-current");
    if (liveVersion) {
      setSelectedHistoryVersion(liveVersion);
    }
  }

  async function runOpsAction(action: "clear-cache" | "build-clusters") {
    setIsOpsBusy(action);
    try {
      if (action === "clear-cache") {
        await browserFetch("/admin/semantic-cache/clear", { method: "POST" });
      } else {
        await browserFetch("/admin/query-mining/clusters/build", { method: "POST" });
      }
      await refresh();
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operation failed.");
    } finally {
      setIsOpsBusy("");
    }
  }

  const comparisonTiles = [
    {
      label: "Latency Delta",
      value:
        typeof comparePayload?.summary?.latency_delta_ms === "number"
          ? `${Number(comparePayload.summary.latency_delta_ms) > 0 ? "+" : ""}${comparePayload.summary.latency_delta_ms} ms`
          : "Pending",
    },
    {
      label: "Citation Delta",
      value:
        typeof comparePayload?.summary?.citation_count_delta === "number"
          ? `${Number(comparePayload.summary.citation_count_delta) > 0 ? "+" : ""}${comparePayload.summary.citation_count_delta}`
          : "Pending",
    },
    {
      label: "Used Chunk Delta",
      value:
        typeof comparePayload?.summary?.used_chunk_delta === "number"
          ? `${Number(comparePayload.summary.used_chunk_delta) > 0 ? "+" : ""}${comparePayload.summary.used_chunk_delta}`
          : "Pending",
    },
  ];
  const cacheStats = (tuningOps.semanticCache.cache || tuningOps.semanticCache) as GenericMap;
  const cachePolicies = Array.isArray(tuningOps.semanticCache.policies) ? tuningOps.semanticCache.policies as GenericMap[] : [];
  const cacheMetrics = (tuningOps.semanticCache.metrics || {}) as GenericMap;
  const activeCachePolicy = cachePolicies.find((policy) => String(policy.status) === "active") || null;
  const activeCacheVersion = (activeCachePolicy?.active_version || {}) as GenericMap;
  const cacheScopeCount =
    (Array.isArray(activeCacheVersion.allow_corpora) ? activeCacheVersion.allow_corpora.length : 0)
    + (Array.isArray(activeCacheVersion.allow_groups) ? activeCacheVersion.allow_groups.length : 0)
    + (Array.isArray(activeCacheVersion.allow_questions) ? activeCacheVersion.allow_questions.length : 0);
  const currentLiveSignature = selectedProfilesSignature(tuningPayload.live_configuration?.selected_profiles);
  const liveHistoryVersions = useMemo(() => {
    const versions = tuningHistory.versions.filter((version) => String(version.config_kind) === "live");
    const currentAnchor = versions.find((version) => String(version.version_label) === "live-current");
    const currentSignature = currentLiveSignature;
    const rollbackTargets = versions.filter((version) => {
      if (String(version.version_label) === "live-current") {
        return false;
      }
      return selectedProfilesSignature(version.selected_profiles) !== currentSignature;
    });
    return [...(currentAnchor ? [currentAnchor] : []), ...rollbackTargets].slice(0, 6);
  }, [currentLiveSignature, tuningHistory.versions]);
  const inspectedHistoryVersion = selectedHistoryVersion && liveHistoryVersions.some((version) => String(version.id || "") === String(selectedHistoryVersion.id || ""))
    ? selectedHistoryVersion
    : liveHistoryVersions[0] || null;

  return (
    <div className="admin-route-page">
      <div className="section-head">
        <div>
          <p className="admin-route-eyebrow">Governed Tuning</p>
          <h1>Model Tuning &amp; Experimentation</h1>
          <p>Compare a governed sandbox candidate against the production live configuration without mutating runtime active profiles.</p>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="tuning-lab-shell-frame">
        <div className="tuning-lab-shell-main">
          <section className="tuning-lab-shell-section">
            <div className="tuning-lab-shell-title-row">
              <h2>Current Live Configuration</h2>
              <span className="tuning-lab-live-badge">Production Active</span>
            </div>
            {isLoading ? (
              <EmptyState title="Loading live configuration..." copy="Resolving the current active profile set and live version metadata." />
            ) : tuningPayload.live_configuration?.version_label ? (
              <div className="tuning-lab-live-spotlight">
                <div className="tuning-lab-live-visual" aria-hidden="true">
                  <div className="tuning-lab-live-orb" />
                </div>
                <div className="tuning-lab-live-meta">
                  <div className="tuning-lab-live-detail-grid">
                    {["llm", "embedding", "reranker", "retrieval"].map((profileType) => {
                      const resolved = liveResolved[profileType] || {};
                      const config = (resolved.config || {}) as GenericMap;
                      return (
                        <article key={profileType} className="tuning-lab-live-detail">
                          <span>{profileTypeLabel(profileType)}</span>
                          <strong>{String(config.display_name || config.model || liveSelected[profileType] || "Configured")}</strong>
                          <small>
                            {profileType === "retrieval"
                              ? `${String(config.default_mode || "hybrid")} base • ${transformSummaryText(config)}`
                              : String(config.model || config.dimension || config.default_mode || liveSelected[profileType] || "resolved")}
                          </small>
                        </article>
                      );
                    })}
                  </div>
                  <div className="tuning-lab-live-footer">
                    <div>
                      <span className="muted-copy">Last Deployment</span>
                      <strong>{formatTimestamp(tuningPayload.live_configuration.updated_at)}</strong>
                    </div>
                    <div>
                      <span className="muted-copy">Live Transform Switches</span>
                      <strong>
                        {`Master ${Boolean(liveRetrievalConfig.query_transform_enabled) ? "on" : "off"} · Rewrite ${Boolean(liveRetrievalConfig.rewrite_enabled) ? "on" : "off"} · Expansion ${Boolean(liveRetrievalConfig.expansion_enabled) ? "on" : "off"} · HyDE ${Boolean(liveRetrievalConfig.hyde_enabled) ? "on" : "off"}`}
                      </strong>
                    </div>
                    <div>
                      <span className="muted-copy">Cache Posture</span>
                      <strong>{activeCachePolicy ? `Scoped Policy Active · ${String(activeCachePolicy.name)} v${String(activeCacheVersion.version_number || "")}` : "Globally Off"}</strong>
                      <small>
                        {activeCachePolicy
                          ? `${cacheScopeCount} eligible scopes · ${String(activeCacheVersion.ttl_seconds || 0)}s TTL · activated ${formatTimestamp(activeCacheVersion.activated_at)}`
                          : "No retrieval or sandbox action can enable caching."}
                      </small>
                    </div>
                    <button type="button" className="button button-secondary" onClick={scrollToVersionHistory}>
                      View Version History
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState title="Live configuration not available." copy="The runtime profile set has not been synced into tuning storage yet." />
            )}
          </section>

          <section className="tuning-lab-shell-section">
            <div className="tuning-lab-shell-title-row tuning-lab-shell-title-row-bottom">
              <div>
                <h2>Experimentation Sandbox</h2>
                <p>Create a candidate configuration to benchmark against production.</p>
              </div>
              <button type="button" className={`tuning-lab-visual-toggle ${visualMode ? "is-on" : ""}`} onClick={() => setVisualMode((current) => !current)}>
                <span>Visual Mode</span>
                <i />
              </button>
            </div>

            <div className="tuning-lab-shell-note">
              <span className="material-symbols-outlined">experiment</span>
              <p>LLM, reranker, retrieval depth, and answer-time context shaping are safe sandbox dimensions here. Embedding swaps remain visible for planning but are not executed in compare yet.</p>
            </div>

            <div className="tuning-lab-sandbox-grid">
              <div className="tuning-lab-sandbox-left">
                <section className="tuning-lab-parameter-card">
                  <strong className="tuning-lab-card-eyebrow">Generation Parameters</strong>
                  <div className="tuning-lab-slider-grid">
                    <Field
                      label=""
                    >
                      <div className="tuning-lab-slider-wrap">
                        <ParameterLabel label="Temperature" tooltip="Controls randomness in generation. Lower values are more deterministic; higher values are more exploratory." />
                        <div className="tuning-lab-slider-value">{tuningControls.temperature.toFixed(1)}</div>
                        <input type="range" min="0" max="2" step="0.1" value={tuningControls.temperature} onChange={(event) => setTuningControls((current) => ({ ...current, temperature: Number(event.target.value) }))} />
                      </div>
                    </Field>

                    <Field
                      label=""
                    >
                      <div className="tuning-lab-slider-wrap">
                        <ParameterLabel label="Top P" tooltip="Limits generation to the most likely next-token pool. Lower values make output more conservative; higher values allow a wider choice set." />
                        <div className="tuning-lab-slider-value">{tuningControls.topP.toFixed(1)}</div>
                        <input type="range" min="0" max="1" step="0.1" value={tuningControls.topP} onChange={(event) => setTuningControls((current) => ({ ...current, topP: Number(event.target.value) }))} />
                      </div>
                    </Field>

                    <Field
                      label=""
                    >
                      <div className="tuning-lab-slider-wrap">
                        <ParameterLabel label="Chunk Size" tooltip="Caps how much text from each retrieved chunk is sent into the answer prompt. It does not change stored chunking, embeddings, or indexing." />
                        <div className="tuning-lab-slider-value">{tuningControls.chunkSize}</div>
                        <input type="range" min="128" max="2048" step="64" value={tuningControls.chunkSize} onChange={(event) => setTuningControls((current) => ({ ...current, chunkSize: Number(event.target.value) }))} />
                      </div>
                    </Field>

                    <Field
                      label=""
                    >
                      <div className="tuning-lab-slider-wrap">
                        <ParameterLabel label="K-Retrieval Count" tooltip="Controls how many retrieved chunks are passed into the answer flow. Higher values add recall but can increase noise and latency." />
                        <div className="tuning-lab-slider-value">{tuningControls.retrievalK}</div>
                        <input type="range" min="1" max="12" step="1" value={tuningControls.retrievalK} onChange={(event) => setTuningControls((current) => ({ ...current, retrievalK: Number(event.target.value) }))} />
                      </div>
                    </Field>
                  </div>
                </section>

                <section className="tuning-lab-selector-card">
                  <div className="tuning-lab-selector-grid">
                    {TUNING_PROFILE_TYPES.filter((profileType) => profileType !== "retrieval").map((profileType) => {
                      const options = tuningPayload.approved_options[profileType] || [];
                          const label = profileTypeLabel(profileType);
                      return (
                            <Field key={profileType} label={label}>
                          {profileType === "embedding" ? (
                            <select value={approvedLiveEmbeddingName || ""} disabled>
                              {options.map((option) => (
                                <option key={String(option.name)} value={String(option.name)}>
                                  {String(option.display_name || option.name)}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <select
                              value={selectedProfiles[profileType] || ""}
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setSelectedProfiles((current) => ({ ...current, [profileType]: nextValue }));
                              }}
                            >
                              <option value="">Select {label}</option>
                              {options.map((option) => (
                                <option key={String(option.name)} value={String(option.name)}>
                                  {String(option.display_name || option.name)}
                                </option>
                              ))}
                            </select>
                          )}
                        </Field>
                      );
                    })}
                  </div>
                  <div className="tuning-lab-selector-note">
                    <p className="tuning-lab-selector-note-strong">Base Retrieval Profile</p>
                    <p>The current live retrieval profile supplies the governed defaults. Use the controls below to test sandbox-only query transformation behavior before promoting.</p>
                  </div>
                  <div className="tuning-lab-slider-grid">
                    <Field label="">
                      <div className="tuning-lab-slider-wrap">
                        <ParameterLabel label="Query Transformation" tooltip="Master switch for rewrite, expansion, and HyDE. If off, all child transforms are ignored." />
                        <ToggleControl
                          label="Query Transformation"
                          enabled={queryTransformEnabled}
                          onToggle={() => updateRetrievalToggle("query_transform_enabled", !queryTransformEnabled)}
                        />
                      </div>
                    </Field>
                    <Field label="">
                      <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                        <ParameterLabel label="Rewrite" tooltip="Runs the rewrite strategy when query transformation is enabled." />
                        <ToggleControl
                          label="Rewrite"
                          enabled={Boolean(candidateRetrievalConfig.rewrite_enabled)}
                          disabled={!queryTransformEnabled}
                          onToggle={() => updateRetrievalToggle("rewrite_enabled", !Boolean(candidateRetrievalConfig.rewrite_enabled))}
                        />
                      </div>
                    </Field>
                    <Field label="">
                      <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                        <ParameterLabel label="Expansion" tooltip="Adds expansion variants when query transformation is enabled." />
                        <ToggleControl
                          label="Expansion"
                          enabled={Boolean(candidateRetrievalConfig.expansion_enabled)}
                          disabled={!queryTransformEnabled}
                          onToggle={() => updateRetrievalToggle("expansion_enabled", !Boolean(candidateRetrievalConfig.expansion_enabled))}
                        />
                      </div>
                    </Field>
                    <Field label="">
                      <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                        <ParameterLabel label="HyDE" tooltip="Adds a hypothetical-document style query when query transformation is enabled." />
                        <ToggleControl
                          label="HyDE"
                          enabled={Boolean(candidateRetrievalConfig.hyde_enabled)}
                          disabled={!queryTransformEnabled}
                          onToggle={() => updateRetrievalToggle("hyde_enabled", !Boolean(candidateRetrievalConfig.hyde_enabled))}
                        />
                      </div>
                    </Field>
                    <Field label="">
                      <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                        <ParameterLabel label="Transform Max Variants" tooltip="Caps how many generated query variants can be used in the candidate retrieval profile." />
                        <div className="tuning-lab-slider-value">{String(candidateRetrievalConfig.transform_max_variants ?? 3)}</div>
                        <input
                          type="range"
                          min="1"
                          max="8"
                          step="1"
                          value={Number(candidateRetrievalConfig.transform_max_variants ?? 3)}
                          disabled={!queryTransformEnabled}
                          onChange={(event) => updateRetrievalNumber("transform_max_variants", Number(event.target.value))}
                        />
                      </div>
                    </Field>
                    <Field label="">
                      <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                        <ParameterLabel label="Transform Timeout (ms)" tooltip="Latency budget for transform execution in the sandbox candidate." />
                        <div className="tuning-lab-slider-value">{String(candidateRetrievalConfig.transform_timeout_ms ?? 750)}</div>
                        <input
                          type="range"
                          min="100"
                          max="2000"
                          step="50"
                          value={Number(candidateRetrievalConfig.transform_timeout_ms ?? 750)}
                          disabled={!queryTransformEnabled}
                          onChange={(event) => updateRetrievalNumber("transform_timeout_ms", Number(event.target.value))}
                        />
                      </div>
                    </Field>
                  </div>
                  <div className="tuning-lab-selector-note">
                    <p className="tuning-lab-selector-note-strong">
                      Available embedding models:{" "}
                      {(
                        tuningPayload.approved_options.embedding || []
                      )
                        .map((option) => String(option.display_name || option.name))
                        .join(" · ")}
                    </p>
                    <p>* Future enhancement: scoped embedding experiments at file, corpus, or folder shadow-index scope.</p>
                  </div>
                </section>
              </div>

              <aside className="tuning-lab-candidate-rail">
                <div className="tuning-lab-candidate-header">
                  <span className="material-symbols-outlined">science</span>
                  <strong>{draftName || "Candidate Draft"}</strong>
                </div>

                <label className="tuning-lab-candidate-input">
                  <span>Candidate Name</span>
                  <input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
                </label>

                <label className="tuning-lab-candidate-input">
                  <span>Candidate Rationale</span>
                  <textarea value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} rows={4} />
                </label>

                <article className="tuning-lab-candidate-stat">
                  <span>Model</span>
                  <strong>{selectedOptionLabels.llm}</strong>
                </article>
                <article className="tuning-lab-candidate-stat">
                  <span>Candidate Retrieval Configuration</span>
                  <strong>{candidateRetrievalSummary(candidateRetrievalConfig, tuningControls.retrievalK)}</strong>
                </article>
                <article className="tuning-lab-candidate-expected">
                  <span>Expected Change</span>
                  <strong>{expectedChange}</strong>
                </article>
                <article className="tuning-lab-candidate-stat">
                  <span>Sandbox Status</span>
                  <strong>
                    {!preparedCandidate
                      ? "Not prepared"
                      : isPreparedCurrent
                        ? `Prepared at ${formatTimestamp(preparedCandidate.prepared_at)}`
                        : "Needs rerun"}
                  </strong>
                </article>

                <div className="tuning-lab-candidate-actions">
                  <button type="button" className="button button-primary tuning-lab-run-button" onClick={prepareSandboxCandidate} disabled={isComparing || isLoading}>
                    Prepare Candidate
                  </button>
                  {editingDraftId ? (
                    <button type="button" className="button button-secondary" onClick={resetDraftForm}>
                      Cancel Edit
                    </button>
                  ) : null}
                </div>
              </aside>
            </div>
          </section>
        </div>
      </section>

      <section className="card tuning-lab-compare-shell">
        <div className="section-head">
          <div>
            <h2>Test &amp; Compare</h2>
            <p>Run the same query against live production and the governed sandbox candidate, while preserving ACL-safe retrieval and provenance.</p>
          </div>
        </div>

        <div className="tuning-lab-compare-input">
          <input value={sampleQuery} onChange={(event) => setSampleQuery(event.target.value)} placeholder="e.g. How does the Q4 liability clause affect subcontracting?" />
          <button type="button" className="button button-primary" onClick={runCompare} disabled={isComparing || isLoading}>
            {isComparing ? "Running Compare..." : "Run Compare"}
          </button>
        </div>

        <div className="tuning-lab-shell-note">
          <span className="material-symbols-outlined">info</span>
          <p>
            {!preparedCandidate
              ? "Workflow: choose the candidate settings, prepare the candidate snapshot, then ask a question with Run Compare."
              : isPreparedCurrent
                ? `Sandbox ready. Compare will run against the prepared candidate snapshot from ${formatTimestamp(preparedCandidate.prepared_at)}.`
                : "Candidate inputs changed after the last sandbox preparation. Prepare Candidate again before compare."}
          </p>
        </div>

        {comparePayload?.warnings?.length ? (
          <div className="tuning-lab-compare-warning">
            {comparePayload.warnings.map((warning, index) => (
              <p key={`${warning.code || index}`}>
                <strong>{String(warning.message || "Sandbox warning")}</strong> {String(warning.detail || "")}
              </p>
            ))}
          </div>
        ) : null}

        <div className="tuning-lab-compare-summary-grid">
          {comparisonTiles.map((tile) => (
            <article key={tile.label}>
              <span>{tile.label}</span>
              <strong>{tile.value}</strong>
            </article>
          ))}
        </div>

        <div className="tuning-lab-compare-grid">
          <article className="tuning-lab-compare-column">
            <div className="tuning-lab-compare-head">
              <h4>Live Production</h4>
              <span>{comparePayload?.live_run ? `${comparePayload.live_run.latency_ms} ms` : "Pending"}</span>
            </div>
            {renderCompareAnswer(comparePayload?.live_run || null, "Run a compare to inspect the live production baseline.")}
            <div className="tuning-lab-compare-metrics">
              {[
                ["Citations", comparePayload?.live_run ? String(comparePayload.live_run.citation_count) : "Pending"],
                ["Used Chunks", comparePayload?.live_run ? String(comparePayload.live_run.used_chunks_count) : "Pending"],
                ["Path", comparePayload?.live_run ? String(comparePayload.live_run.retrieval_summary?.retrieval_path || comparePayload.live_run.mode || "unknown") : "Pending"],
                ["Transform", comparePayload?.live_run ? transformSummaryText(comparePayload.live_run.retrieval_summary?.transform_summary) : "Pending"],
              ].map(([label, value]) => (
                <div key={label}>
                  <p>{label}</p>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="tuning-lab-compare-column">
            <div className="tuning-lab-compare-head tuning-lab-compare-head-candidate">
              <h4>{draftName || "Candidate Draft"} (Sandbox)</h4>
              <span>
                {comparePayload?.candidate_run?.status === "completed"
                  ? `${comparePayload.candidate_run.latency_ms} ms`
                  : comparePayload?.candidate_run?.status === "blocked_embedding_scope"
                    ? "Not executed"
                    : "Pending"}
              </span>
            </div>
            {renderCompareAnswer(comparePayload?.candidate_run || null, "Run a compare to inspect the sandbox candidate result.")}
            <div className="tuning-lab-compare-metrics tuning-lab-compare-metrics-candidate">
              {[
                ["Citations", comparePayload?.candidate_run?.status === "completed" ? String(comparePayload.candidate_run.citation_count) : "Blocked"],
                ["Used Chunks", comparePayload?.candidate_run?.status === "completed" ? String(comparePayload.candidate_run.used_chunks_count) : "Blocked"],
                ["Path", comparePayload?.candidate_run?.status === "completed" ? String(comparePayload.candidate_run.retrieval_summary?.retrieval_path || comparePayload.candidate_run.mode || "unknown") : "Blocked"],
                ["Transform", comparePayload?.candidate_run ? transformSummaryText(comparePayload.candidate_run.retrieval_summary?.transform_summary) : "Blocked"],
              ].map(([label, value]) => (
                <div key={label}>
                  <p>{label}</p>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <footer className="tuning-lab-action-footer">
        <button type="button" className="button button-secondary" onClick={resetDraftForm}>
          Discard Candidate
        </button>
        <input className="tuning-lab-promotion-note" value={promotionNote} onChange={(event) => setPromotionNote(event.target.value)} aria-label="Promotion note" />
        <span className="tuning-lab-draft-state">
          {editingDraftId ? (hasUnsavedDraftChanges ? "Draft has unsaved changes" : "Draft saved") : "Save draft before promotion"}
        </span>
        <button type="button" className="button button-secondary" onClick={saveDraft} disabled={savingDraft || (Boolean(editingDraftId) && !hasUnsavedDraftChanges)}>
          {savingDraft ? "Saving Draft..." : editingDraftId ? "Update Draft" : "Save as Draft"}
        </button>
        <button type="button" className="button button-secondary" onClick={runEvalPack} disabled={isEvaluating || savingDraft || !editingDraftId}>
          {isEvaluating ? "Running Eval Pack..." : "Run Eval Pack"}
        </button>
        <span className="tuning-lab-draft-state">
          {evalRun
            ? `Eval gate: ${String(evalRun.gate_status)} · recall@5 ${Number((evalRun.gate_aggregates as GenericMap)?.recall_at_5 ?? NaN).toFixed(3)} · MRR ${Number((evalRun.gate_aggregates as GenericMap)?.mrr ?? NaN).toFixed(3)}${(evalRun.deltas_vs_live_baseline as GenericMap) ? ` · vs live: recall@5 Δ ${formatMetricDelta((evalRun.deltas_vs_live_baseline as GenericMap)?.recall_at_5)} · MRR Δ ${formatMetricDelta((evalRun.deltas_vs_live_baseline as GenericMap)?.mrr)}` : ""}`
            : "No eval evidence yet — promotion is blocked in require mode"}
        </span>
        <button
          type="button"
          className="button button-primary"
          onClick={promoteCandidate}
          disabled={isPromoting || savingDraft || (evalRun ? evalRun.gate_status !== "pass" : false)}
        >
          {isPromoting ? "Promoting..." : evalRun && evalRun.gate_status !== "pass" ? "Eval Gate Failed" : "Promote to Live"}
        </button>
      </footer>

      <section className="card tuning-lab-history-shell" ref={historySectionRef}>
        <div className="section-head">
          <div>
            <h2>Version History &amp; Rollback</h2>
            <p>Promoted versions remain visible so operators can recover the prior live configuration with an audited rollback.</p>
          </div>
        </div>
        <div className="tuning-lab-history-grid">
          {liveHistoryVersions.map((version) => {
            const status = String(version.status || "version");
            const versionSignature = selectedProfilesSignature(version.selected_profiles);
            const matchesCurrentProduction = versionSignature === currentLiveSignature;
            const isCurrentAnchor = String(version.version_label) === "live-current";
            const statusLabel = isCurrentAnchor ? "current live" : matchesCurrentProduction ? "current config" : status;
            const isSelected = String(inspectedHistoryVersion?.id || "") === String(version.id || "");
            return (
              <article key={String(version.id)} className={`tuning-lab-history-card ${isSelected ? "is-selected" : ""}`} onClick={() => setSelectedHistoryVersion(version)}>
                <div className="tuning-lab-history-status">
                  <span className={`tuning-lab-status-dot ${isCurrentAnchor ? "is-live" : "is-archived"}`} />
                  <span>{statusLabel}</span>
                </div>
                <strong>{String(version.name || "Live configuration")}</strong>
                <p>{formatTimestamp(version.updated_at || version.created_at)}</p>
                <div className="tuning-lab-history-summary">
                  <span>{versionProfileName(version, "llm")}</span>
                  <span>{versionProfileName(version, "reranker")}</span>
                  <span>{transformSummaryText(versionProfileConfig(version, "retrieval"))}</span>
                </div>
                <button type="button" className="button button-secondary" onClick={(event) => { event.stopPropagation(); rollbackVersion(String(version.version_label)); }} disabled={isRollingBack || matchesCurrentProduction}>
                  {matchesCurrentProduction ? "Already Live" : "Roll Back"}
                </button>
              </article>
            );
          })}
        </div>
        {inspectedHistoryVersion ? (
          <div className="tuning-lab-version-detail">
            <div className="tuning-lab-version-detail-head">
              <div>
                <span className="muted-copy">Selected Version</span>
                <strong>{String(inspectedHistoryVersion.name || "Live configuration")}</strong>
              </div>
              <span>{formatTimestamp(inspectedHistoryVersion.updated_at || inspectedHistoryVersion.created_at)}</span>
            </div>
            <div className="tuning-lab-version-detail-grid">
              {(["llm", "embedding", "reranker", "retrieval"] as const).map((profileType) => (
                <article key={profileType}>
                  <span>{profileTypeLabel(profileType)}</span>
                  <strong>{versionProfileName(inspectedHistoryVersion, profileType)}</strong>
                  <p>{versionModelDetail(inspectedHistoryVersion, profileType)}</p>
                </article>
              ))}
            </div>
            {(() => {
              const event = tuningHistory.promotion_events.find(
                (item) => String(item.new_live_version_label) === String(inspectedHistoryVersion.version_label)
              );
              const summary = evalEvidenceSummary((event?.eval_evidence_json || null) as GenericMap | null);
              return (
                <p className="muted-copy">
                  Eval evidence: {summary || "none recorded (pre-AR4 promotion or evidence-free warn-mode action)"}
                </p>
              );
            })()}
          </div>
        ) : null}
      </section>

      <section className="card tuning-lab-cache-governance">
        <div className="section-head">
          <div>
            <h2>Semantic Cache Governance</h2>
            <p>Global default: Off. No answer is cached unless it matches an activated scoped policy.</p>
          </div>
          <span className={`badge ${activeCachePolicy ? "is-good" : ""}`}>{activeCachePolicy ? "Scoped Policy Active" : "Globally Off"}</span>
        </div>
        <div className="tuning-lab-cache-metrics">
          <article><span>Active Policy</span><strong>{activeCachePolicy ? `${String(activeCachePolicy.name)} · v${String(activeCacheVersion.version_number || "")}` : "None"}</strong></article>
          <article><span>Eligible Scopes</span><strong>{cacheScopeCount}</strong></article>
          <article><span>TTL / Capacity</span><strong>{activeCachePolicy ? `${String(activeCacheVersion.ttl_seconds || 0)}s · ${String(activeCacheVersion.max_active_entries || 0)} entries` : "Not active"}</strong></article>
          <article><span>Hits / Misses / Refreshes</span><strong>{`${String(cacheMetrics.hit_count || 0)} / ${String(cacheMetrics.miss_count || 0)} / ${String(cacheMetrics.refresh_count || 0)}`}</strong></article>
          <article><span>Active Entries</span><strong>{String(cacheStats.active_entries || 0)}</strong></article>
          <article><span>Validation Health</span><strong>{Number(cacheMetrics.reauthorization_miss_count || 0) === 0 ? "Healthy" : `${String(cacheMetrics.reauthorization_miss_count)} blocked stale reuses`}</strong></article>
        </div>
        <div className="toolbar-inline">
          <Link className="button button-primary" href="/console/admin/profiles/cache-policy">Manage Cache Policy</Link>
          <button type="button" className="button button-secondary" disabled={isOpsBusy !== "" || !activeCachePolicy} onClick={() => runOpsAction("clear-cache")}>
            {isOpsBusy === "clear-cache" ? "Clearing..." : "Clear Active Entries"}
          </button>
        </div>
      </section>

      <section className="card tuning-lab-ops-shell">
        <div className="section-head">
          <div>
            <h2>Retrieval Ops Guardrails</h2>
            <p>Rollout safety, transform observability, query mining, and misuse governance remain visible here.</p>
          </div>
          <span className="badge is-good">M17.b.3 → M21</span>
        </div>

        <div className="tuning-lab-ops-grid">
          <article className="tuning-lab-ops-card">
            <span>Query Transformation</span>
            <strong>{transformSummaryText((liveResolved.retrieval || {}).config)}</strong>
            <p>{`Live retrieval profile ${String(liveSelected.retrieval || "default")} controls rewrite, expansion, and HyDE. Decisions are stored in retrieval traces and now visible in sandbox compare output.`}</p>
          </article>

          <article className="tuning-lab-ops-card">
            <span>Query Mining</span>
            <strong>{tuningOps.queryMining.clusters.length} failure clusters</strong>
            <p>{tuningOps.queryMining.events.length} recent events and {tuningOps.queryMining.eval_packs.length} derived eval packs are available for release gating.</p>
            <button type="button" className="button button-secondary" disabled={isOpsBusy !== ""} onClick={() => runOpsAction("build-clusters")}>
              {isOpsBusy === "build-clusters" ? "Building..." : "Build Clusters"}
            </button>
          </article>

          <article className="tuning-lab-ops-card tuning-lab-ops-card-warning">
            <span>Misuse Governance</span>
            <strong>{tuningOps.governance.risk_signals.length} risk signals</strong>
            <p>{tuningOps.governance.restrictions.length} active/recent restrictions. Blocks remain reversible and audit-backed.</p>
          </article>
        </div>
      </section>
    </div>
  );
}
