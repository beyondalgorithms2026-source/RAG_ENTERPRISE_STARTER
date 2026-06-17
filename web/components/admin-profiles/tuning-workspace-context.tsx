"use client";

import { MaterialIcon } from "@/components/icons";
import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";
import { browserFetch } from "@/lib/api-browser";
import { tuningEndpoints } from "./endpoints";

export type GenericMap = Record<string, unknown>;
export type RuntimeSetting = { effective: unknown; override: unknown; source: string };

export type TuningPayload = {
  live_configuration: GenericMap;
  candidate_drafts: GenericMap[];
  approved_options: Record<string, GenericMap[]>;
  profile_types: string[];
};

export type TuningHistory = {
  promotion_events: GenericMap[];
  versions: GenericMap[];
};

export type TuningOpsPayload = {
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

export type RetrievalEvidence = {
  limitations: string;
  global_control: {
    before?: Record<string, number>;
    after?: Record<string, number>;
    after_gate?: { status?: string };
  };
  evidence: Array<{
    feature: string;
    verdict: string;
    chosen?: string | null;
    variants: Array<{
      name: string;
      deltas: Record<string, number | null>;
      feature_metric?: { name: string; delta: number | null } | null;
      passes: boolean;
    }>;
  }>;
};

export type CompareRun = {
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

export type ComparePayload = {
  live_run: CompareRun;
  candidate_run: CompareRun | null;
  summary: GenericMap;
  warnings: GenericMap[];
  preconditions: GenericMap[];
};

export type PreparedCandidate = {
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

export const TUNING_PROFILE_TYPES = ["llm", "embedding", "reranker", "retrieval"] as const;

export function profileTypeLabel(profileType: string) {
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

export function transformSummaryText(value: unknown) {
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

export function candidateRetrievalSummary(config: Record<string, unknown>, retrievalK: number) {
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
  if (config.multi_query_enabled) {
    parts.push("Multi-query fan-out");
  }
  return parts.join(" · ");
}

export function formatMetricDelta(value: unknown) {
  if (typeof value !== "number") {
    return "n/a";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
}

export function evalEvidenceSummary(evidence: GenericMap | null | undefined) {
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

export function formatTimestamp(value: unknown) {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

export function versionResolvedConfig(version: GenericMap, profileType: string) {
  return ((((version.resolved_config || {}) as GenericMap)[profileType] || {}) as GenericMap);
}

export function versionProfileConfig(version: GenericMap, profileType: string) {
  return ((versionResolvedConfig(version, profileType).config || {}) as GenericMap);
}

export function versionProfileName(version: GenericMap, profileType: string) {
  return String(versionProfileConfig(version, profileType).display_name || versionResolvedConfig(version, profileType).profile_name || (((version.selected_profiles || {}) as GenericMap)[profileType] || "default"));
}

export function versionModelDetail(version: GenericMap, profileType: string) {
  const config = versionProfileConfig(version, profileType);
  if (profileType === "retrieval") {
    return `${String(config.default_mode || "hybrid")} base · ${transformSummaryText(config)}`;
  }
  return String(config.model || config.dimension || versionProfileName(version, profileType));
}

export function selectedProfilesSignature(value: unknown) {
  const profiles = (value || {}) as GenericMap;
  return JSON.stringify(
    TUNING_PROFILE_TYPES.reduce<Record<string, string>>((payload, profileType) => {
      payload[profileType] = String(profiles[profileType] || "");
      return payload;
    }, {})
  );
}

export function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="admin-empty-state">
      <MaterialIcon name="inbox" />
      <strong>{title}</strong>
      <p>{copy}</p>
    </div>
  );
}

export function ParameterLabel({ label, tooltip }: { label: string; tooltip: string }) {
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

export function renderCompareAnswer(run: CompareRun | null, emptyCopy: string) {
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


function useTuningWorkspaceState() {
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
  const [retrievalEvidence, setRetrievalEvidence] = useState<RetrievalEvidence | null>(null);
  const [visualMode, setVisualMode] = useState(true);
  const [preparedCandidate, setPreparedCandidate] = useState<PreparedCandidate | null>(null);
  const [savedDraftSignature, setSavedDraftSignature] = useState("");
  const [selectedHistoryVersion, setSelectedHistoryVersion] = useState<GenericMap | null>(null);
  const [draftName, setDraftName] = useState("Balanced candidate");
  const [draftDescription, setDraftDescription] = useState("Interactive sandbox candidate for side-by-side compare against the live baseline.");
  const [sampleQuery, setSampleQuery] = useState("How does the Q4 liability clause affect subcontracting?");
  const [promotionNote, setPromotionNote] = useState("Validated in sandbox compare.");
  const [evalEnforcement, setEvalEnforcement] = useState<RuntimeSetting>({ effective: "require", override: null, source: "default" });
  const [approvalActor, setApprovalActor] = useState("");
  const [savingEnforcement, setSavingEnforcement] = useState(false);
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
      const tuning = await browserFetch<TuningPayload>(tuningEndpoints.configurations);
      const history = await browserFetch<TuningHistory>(tuningEndpoints.history);
      const [semanticCache, queryMiningPayload, governance, evidence, runtimeSettings] = await Promise.all([
        browserFetch<GenericMap>(tuningEndpoints.semanticCache),
        browserFetch<GenericMap>(tuningEndpoints.queryMining),
        browserFetch<TuningOpsPayload["governance"]>(tuningEndpoints.governance),
        browserFetch<RetrievalEvidence>(tuningEndpoints.retrievalEvidence),
        browserFetch<{ settings: Record<string, RuntimeSetting> }>(tuningEndpoints.runtimeSettings).catch(() => null),
      ]);
      const queryMining = {
        events: ((queryMiningPayload.events || queryMiningPayload.query_events || []) as GenericMap[]),
        clusters: ((queryMiningPayload.clusters || []) as GenericMap[]),
        eval_packs: ((queryMiningPayload.eval_packs || queryMiningPayload.derived_eval_packs || []) as GenericMap[]),
      };
      setTuningPayload(tuning);
      setTuningHistory(history);
      setTuningOps({ semanticCache, queryMining, governance });
      setRetrievalEvidence(evidence);
      if (runtimeSettings?.settings.tuning_eval_enforcement) {
        setEvalEnforcement(runtimeSettings.settings.tuning_eval_enforcement);
      }
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
        const response = await browserFetch<{ draft: GenericMap }>(tuningEndpoints.drafts, { method: "POST", json: payload });
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
      const compare = await browserFetch<ComparePayload>(tuningEndpoints.compare, {
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
      const response = await browserFetch<{ eval_run: GenericMap }>(tuningEndpoints.evalRuns, {
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
      await browserFetch(tuningEndpoints.promote, {
        method: "POST",
        headers: approvalActor.trim() ? { "X-Approval-Actor": approvalActor.trim() } : undefined,
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
      await browserFetch(tuningEndpoints.rollback, {
        method: "POST",
        headers: approvalActor.trim() ? { "X-Approval-Actor": approvalActor.trim() } : undefined,
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

  async function saveEvalEnforcement(value: string | null) {
    setSavingEnforcement(true);
    try {
      const response = await browserFetch<{ settings: Record<string, RuntimeSetting> }>(tuningEndpoints.runtimeSettings, {
        method: "PATCH",
        headers: approvalActor.trim() ? { "X-Approval-Actor": approvalActor.trim() } : undefined,
        json: { key: "tuning_eval_enforcement", value },
      });
      setEvalEnforcement(response.settings.tuning_eval_enforcement);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update evaluation enforcement.");
    } finally {
      setSavingEnforcement(false);
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
        await browserFetch(tuningEndpoints.semanticCacheClear, { method: "POST" });
      } else {
        await browserFetch(tuningEndpoints.queryMiningBuild, { method: "POST" });
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


  return { historySectionRef, tuningPayload, comparePayload, error, isLoading, isComparing, savingDraft, isPromoting, isRollingBack, isEvaluating, evalRun, isOpsBusy, editingDraftId, tuningHistory, tuningOps, retrievalEvidence, visualMode, preparedCandidate, draftName, draftDescription, sampleQuery, promotionNote, evalEnforcement, approvalActor, savingEnforcement, selectedProfiles, candidateRetrievalConfig, tuningControls, liveSelected, liveResolved, liveRetrievalConfig, approvedLiveEmbeddingName, effectiveSelectedProfiles, isPreparedCurrent, hasUnsavedDraftChanges, selectedOptionLabels, queryTransformEnabled, expectedChange, comparisonTiles, cacheStats, cacheMetrics, activeCachePolicy, activeCacheVersion, cacheScopeCount, currentLiveSignature, liveHistoryVersions, inspectedHistoryVersion, setVisualMode, setSelectedProfiles, setTuningControls, setDraftName, setDraftDescription, setSampleQuery, setPromotionNote, setApprovalActor, setSelectedHistoryVersion, updateRetrievalToggle, updateRetrievalNumber, resetDraftForm, prepareSandboxCandidate, saveDraft, runCompare, runEvalPack, promoteCandidate, rollbackVersion, saveEvalEnforcement, scrollToVersionHistory, runOpsAction };
}

type TuningWorkspace = ReturnType<typeof useTuningWorkspaceState>;
const TuningWorkspaceContext = createContext<TuningWorkspace | null>(null);

export function TuningWorkspaceProvider({ children }: { children: ReactNode }) {
  const workspace = useTuningWorkspaceState();
  return <TuningWorkspaceContext.Provider value={workspace}>{children}</TuningWorkspaceContext.Provider>;
}

export function useTuningWorkspace() {
  const workspace = useContext(TuningWorkspaceContext);
  if (!workspace) throw new Error("useTuningWorkspace must be used inside TuningWorkspaceProvider");
  return workspace;
}
