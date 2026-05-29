"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";

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
const GOVERNED_MODEL_TYPES = ["llm", "embedding", "reranker"] as const;

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

  const liveSelected = (tuningPayload.live_configuration?.selected_profiles || {}) as Record<string, string>;
  const liveResolved = (tuningPayload.live_configuration?.resolved_config || {}) as Record<string, GenericMap>;
  const candidateSignature = JSON.stringify({
    draftId: editingDraftId,
    name: draftName,
    description: draftDescription,
    selectedProfiles,
    tuningControls,
  });
  const isPreparedCurrent = preparedCandidate ? preparedCandidate.signature === candidateSignature : false;
  const selectedOptionLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const profileType of TUNING_PROFILE_TYPES) {
      const selected = selectedProfiles[profileType] || liveSelected[profileType] || "";
      const options = tuningPayload.approved_options[profileType] || [];
      const match = options.find((option) => String(option.name) === selected);
      labels[profileType] = String(match?.display_name || match?.name || selected || "Not selected");
    }
    return labels;
  }, [liveSelected, selectedProfiles, tuningPayload]);

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
      if ((selectedProfiles[profileType] || "") && selectedProfiles[profileType] !== (liveSelected[profileType] || "")) {
        deltaCount += 1;
      }
    }
    if (deltaCount === 0) {
      return "No governed profile swaps yet; this candidate mirrors the live baseline and only tests answer-time controls.";
    }
    return `${deltaCount} governed profile selections differ from production; use sandbox compare before any later rollout step.`;
  }, [comparePayload, liveSelected, selectedProfiles]);

  function resetDraftForm() {
    setEditingDraftId(null);
    setPreparedCandidate(null);
    setDraftName("Balanced candidate");
    setDraftDescription("Interactive sandbox candidate for side-by-side compare against the live baseline.");
    setSelectedProfiles({
      llm: liveSelected.llm || "",
      embedding: liveSelected.embedding || "",
      reranker: liveSelected.reranker || "",
      retrieval: liveSelected.retrieval || "",
    });
    setComparePayload(null);
  }

  function prepareSandboxCandidate() {
    setPreparedCandidate({
      draft_id: editingDraftId,
      name: draftName,
      description: draftDescription,
      selected_profiles: { ...selectedProfiles },
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
        selected_profiles: selectedProfiles,
      };
      if (editingDraftId) {
        const response = await browserFetch<{ draft: GenericMap }>(`/admin/tuning/drafts/${editingDraftId}`, { method: "PATCH", json: payload });
        setEditingDraftId(Number(response.draft.id));
      } else {
        const response = await browserFetch<{ draft: GenericMap }>("/admin/tuning/drafts", { method: "POST", json: payload });
        setEditingDraftId(Number(response.draft.id));
      }
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
      setError("Sandbox inputs changed after preparation. Run Sandbox Test again to refresh the candidate snapshot before compare.");
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
                    {["llm", "embedding", "reranker"].map((profileType) => {
                      const resolved = liveResolved[profileType] || {};
                      const config = (resolved.config || {}) as GenericMap;
                      return (
                        <article key={profileType} className="tuning-lab-live-detail">
                          <span>{profileType === "llm" ? "Inference Model" : profileType === "embedding" ? "Embedding" : "Reranker"}</span>
                          <strong>{String(config.display_name || config.model || liveSelected[profileType] || "Configured")}</strong>
                          <small>{String(config.model || config.dimension || config.default_mode || liveSelected[profileType] || "resolved")}</small>
                        </article>
                      );
                    })}
                  </div>
                  <div className="tuning-lab-live-footer">
                    <div>
                      <span className="muted-copy">Last Deployment</span>
                      <strong>{formatTimestamp(tuningPayload.live_configuration.updated_at)}</strong>
                    </div>
                    <button type="button" className="button button-secondary" disabled>
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
                    {GOVERNED_MODEL_TYPES.map((profileType) => {
                      const options = tuningPayload.approved_options[profileType] || [];
                      const label = profileType === "llm" ? "Inference Model" : profileType === "embedding" ? "Embedding Model" : "Reranking Logic";
                      return (
                        <Field key={profileType} label={label}>
                          {profileType === "embedding" ? (
                            <select value={liveSelected.embedding || ""} disabled>
                              {options.map((option) => (
                                <option key={String(option.name)} value={String(option.name)}>
                                  {String(option.display_name || option.name)}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <select value={selectedProfiles[profileType] || ""} onChange={(event) => setSelectedProfiles((current) => ({ ...current, [profileType]: event.target.value }))}>
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
                  <span>Context Strategy</span>
                  <strong>{selectedOptionLabels.retrieval}</strong>
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
                    Run Sandbox Test
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
              ? "Workflow: choose the candidate settings, run Sandbox Test to freeze the candidate snapshot, then ask a question with Run Compare."
              : isPreparedCurrent
                ? `Sandbox ready. Compare will run against the prepared candidate snapshot from ${formatTimestamp(preparedCandidate.prepared_at)}.`
                : "Candidate inputs changed after the last sandbox preparation. Run Sandbox Test again before compare."}
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
        <button type="button" className="button button-secondary" onClick={saveDraft} disabled={savingDraft}>
          {savingDraft ? "Saving Draft..." : editingDraftId ? "Update Draft" : "Save as Draft"}
        </button>
        <button type="button" className="button button-primary" onClick={promoteCandidate} disabled={isPromoting || savingDraft}>
          {isPromoting ? "Promoting..." : "Promote to Live"}
        </button>
      </footer>

      <section className="card tuning-lab-history-shell">
        <div className="section-head">
          <div>
            <h2>Version History &amp; Rollback</h2>
            <p>Promoted versions remain visible so operators can recover the prior live configuration with an audited rollback.</p>
          </div>
        </div>
        <div className="tuning-lab-history-grid">
          {tuningHistory.versions
            .filter((version) => String(version.config_kind) === "live")
            .slice(0, 6)
            .map((version) => (
              <article key={String(version.id)} className="tuning-lab-history-card">
                <span>{String(version.status || "version")}</span>
                <strong>{String(version.version_label)}</strong>
                <p>{String(version.name || "Live configuration")}</p>
                <button type="button" className="button button-secondary" onClick={() => rollbackVersion(String(version.version_label))} disabled={isRollingBack || String(version.version_label) === "live-current"}>
                  Roll Back
                </button>
              </article>
            ))}
        </div>
      </section>

      <section className="card tuning-lab-ops-shell">
        <div className="section-head">
          <div>
            <h2>Retrieval Ops Guardrails</h2>
            <p>Later M17.b.3-M21 capabilities are visible here: rollout safety, transform observability, semantic cache health, query mining, and misuse governance.</p>
          </div>
          <span className="badge is-good">M17.b.3 → M21</span>
        </div>

        <div className="tuning-lab-ops-grid">
          <article className="tuning-lab-ops-card">
            <span>Query Transformation</span>
            <strong>Disabled by default</strong>
            <p>Rewrite, expansion, and HyDE decisions are stored in retrieval traces when enabled on the active retrieval profile.</p>
          </article>

          <article className="tuning-lab-ops-card">
            <span>Semantic Cache</span>
            <strong>{String(cacheStats.active_entries ?? 0)} active entries</strong>
            <p>{String(cacheStats.hit_count ?? 0)} recorded hits. Cache keys include ACL scope, profile snapshot, corpus scope, and retrieval mode.</p>
            <button type="button" className="button button-secondary" disabled={isOpsBusy !== ""} onClick={() => runOpsAction("clear-cache")}>
              {isOpsBusy === "clear-cache" ? "Clearing..." : "Clear Cache"}
            </button>
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
