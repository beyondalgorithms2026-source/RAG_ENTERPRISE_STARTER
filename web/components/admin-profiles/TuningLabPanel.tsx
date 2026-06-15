"use client";

import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";
import { Field } from "@/components/ui/Field";
import { Toggle } from "@/components/ui/Toggle";
import {
  EmptyState, ParameterLabel, TUNING_PROFILE_TYPES, candidateRetrievalSummary, type GenericMap,
  evalEvidenceSummary, formatMetricDelta, formatTimestamp, profileTypeLabel,
  renderCompareAnswer, selectedProfilesSignature, transformSummaryText,
  useTuningWorkspace, versionModelDetail, versionProfileConfig, versionProfileName,
} from "./tuning-workspace-context";

function ToggleControl({ label, enabled, onToggle, disabled = false }: { label: string; enabled: boolean; onToggle: () => void; disabled?: boolean }) {
  return <Toggle variant="switch" label={`${label} ${enabled ? "On" : "Off"}`} checked={enabled} disabled={disabled} onChange={onToggle} />;
}

export function TuningLabPanel() {
  const { historySectionRef, tuningPayload, comparePayload, error, isLoading, isComparing, savingDraft, isPromoting, isRollingBack, isEvaluating, evalRun, isOpsBusy, editingDraftId, tuningHistory, tuningOps, retrievalEvidence, visualMode, preparedCandidate, draftName, draftDescription, sampleQuery, promotionNote, evalEnforcement, approvalActor, savingEnforcement, selectedProfiles, candidateRetrievalConfig, tuningControls, liveSelected, liveResolved, liveRetrievalConfig, approvedLiveEmbeddingName, effectiveSelectedProfiles, isPreparedCurrent, hasUnsavedDraftChanges, selectedOptionLabels, queryTransformEnabled, expectedChange, comparisonTiles, cacheStats, cacheMetrics, activeCachePolicy, activeCacheVersion, cacheScopeCount, currentLiveSignature, liveHistoryVersions, inspectedHistoryVersion, setVisualMode, setSelectedProfiles, setTuningControls, setDraftName, setDraftDescription, setSampleQuery, setPromotionNote, setApprovalActor, setSelectedHistoryVersion, updateRetrievalToggle, updateRetrievalNumber, resetDraftForm, prepareSandboxCandidate, saveDraft, runCompare, runEvalPack, promoteCandidate, rollbackVersion, saveEvalEnforcement, scrollToVersionHistory, runOpsAction } = useTuningWorkspace();
  return (
    <>
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
                    <button type="button" title="Switch between the guided visual editor and the raw parameter form. Display only — it does not change what gets saved." className={`tuning-lab-visual-toggle ${visualMode ? "is-on" : ""}`} onClick={() => setVisualMode((current) => !current)}>
                      <span>Visual Mode</span>
                      <i />
                    </button>
                  </div>
      
                  <div className="tuning-lab-shell-note">
                    <span className="material-symbols-outlined">experiment</span>
                    <p>LLM, reranker, retrieval depth, and answer-time context shaping are safe sandbox dimensions here. Embedding swaps remain visible for planning but are not executed in compare yet.</p>
                  </div>
      
                  {retrievalEvidence ? (
                    <section className="tuning-lab-parameter-card">
                      <strong className="tuning-lab-card-eyebrow" title="Eval-proven verdict for each retrieval enhancement (the AR14 ablation): which features were adopted and their measured gain. Further tuning is gated by this evidence.">Retrieval tuning evidence</strong>
                      <p>
                        Global gate: {String(retrievalEvidence.global_control.after_gate?.status || "pending")}.
                        Only paired non-regressing gains remain configurable.
                      </p>
                      <div className="admin-inline-list">
                        {retrievalEvidence.evidence.map((item) => {
                          const chosen = item.variants.find((variant) => variant.name === item.chosen);
                          const gain = chosen?.feature_metric?.delta ?? chosen?.deltas?.ndcg_at_10;
                          return (
                            <span key={item.feature} className={`status-chip ${item.verdict === "adopted" ? "is-success" : "is-warning"}`}>
                              {item.feature.replaceAll("_", " ")}: {item.verdict}
                              {item.chosen ? ` (${item.chosen}${typeof gain === "number" ? `, +${gain.toFixed(3)}` : ""})` : ""}
                            </span>
                          );
                        })}
                      </div>
                      <small>{retrievalEvidence.limitations}</small>
                    </section>
                  ) : null}
      
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
                              <TextInput type="range" min="0" max="2" step="0.1" value={tuningControls.temperature} onChange={(event) => setTuningControls((current) => ({ ...current, temperature: Number(event.target.value) }))} />
                            </div>
                          </Field>
      
                          <Field
                            label=""
                          >
                            <div className="tuning-lab-slider-wrap">
                              <ParameterLabel label="Top P" tooltip="Limits generation to the most likely next-token pool. Lower values make output more conservative; higher values allow a wider choice set." />
                              <div className="tuning-lab-slider-value">{tuningControls.topP.toFixed(1)}</div>
                              <TextInput type="range" min="0" max="1" step="0.1" value={tuningControls.topP} onChange={(event) => setTuningControls((current) => ({ ...current, topP: Number(event.target.value) }))} />
                            </div>
                          </Field>
      
                          <Field
                            label=""
                          >
                            <div className="tuning-lab-slider-wrap">
                              <ParameterLabel label="Chunk Size" tooltip="Caps how much text from each retrieved chunk is sent into the answer prompt. It does not change stored chunking, embeddings, or indexing." />
                              <div className="tuning-lab-slider-value">{tuningControls.chunkSize}</div>
                              <TextInput type="range" min="128" max="2048" step="64" value={tuningControls.chunkSize} onChange={(event) => setTuningControls((current) => ({ ...current, chunkSize: Number(event.target.value) }))} />
                            </div>
                          </Field>
      
                          <Field
                            label=""
                          >
                            <div className="tuning-lab-slider-wrap">
                              <ParameterLabel label="K-Retrieval Count" tooltip="Controls how many retrieved chunks are passed into the answer flow. Higher values add recall but can increase noise and latency." />
                              <div className="tuning-lab-slider-value">{tuningControls.retrievalK}</div>
                              <TextInput type="range" min="1" max="12" step="1" value={tuningControls.retrievalK} onChange={(event) => setTuningControls((current) => ({ ...current, retrievalK: Number(event.target.value) }))} />
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
                                  <Select value={approvedLiveEmbeddingName || ""} disabled>
                                    {options.map((option) => (
                                      <option key={String(option.name)} value={String(option.name)}>
                                        {String(option.display_name || option.name)}
                                      </option>
                                    ))}
                                  </Select>
                                ) : (
                                  <Select
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
                                  </Select>
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
                              <ParameterLabel label="Multi-query fan-out" tooltip="Retrieve each generated variant separately and RRF-fuse, instead of concatenating variants into one query." />
                              <ToggleControl
                                label="Multi-query fan-out"
                                enabled={Boolean(candidateRetrievalConfig.multi_query_enabled)}
                                disabled={!queryTransformEnabled}
                                onToggle={() => updateRetrievalToggle("multi_query_enabled", !Boolean(candidateRetrievalConfig.multi_query_enabled))}
                              />
                            </div>
                          </Field>
                          <Field label="">
                            <div className={`tuning-lab-slider-wrap ${queryTransformEnabled ? "" : "is-disabled"}`}>
                              <ParameterLabel label="Transform Max Variants" tooltip="Caps how many generated query variants can be used in the candidate retrieval profile." />
                              <div className="tuning-lab-slider-value">{String(candidateRetrievalConfig.transform_max_variants ?? 3)}</div>
                              <TextInput
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
                              <TextInput
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
                        <TextInput value={draftName} onChange={(event) => setDraftName(event.target.value)} />
                      </label>
      
                      <label className="tuning-lab-candidate-input">
                        <span>Candidate Rationale</span>
                        <Textarea value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} rows={4} />
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
    </>
  );
}
