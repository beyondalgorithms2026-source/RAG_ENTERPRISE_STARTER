"use client";

import { MaterialIcon } from "@/components/icons";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";
import {
  EmptyState, ParameterLabel, TUNING_PROFILE_TYPES, candidateRetrievalSummary, type GenericMap,
  evalEvidenceSummary, formatMetricDelta, formatTimestamp, profileTypeLabel,
  renderCompareAnswer, selectedProfilesSignature, transformSummaryText,
  useTuningWorkspace, versionModelDetail, versionProfileConfig, versionProfileName,
} from "./tuning-workspace-context";

export function EvalEvidencePanel() {
  const { historySectionRef, tuningPayload, comparePayload, error, isLoading, isComparing, savingDraft, isPromoting, isRollingBack, isEvaluating, evalRun, isOpsBusy, editingDraftId, tuningHistory, tuningOps, retrievalEvidence, visualMode, preparedCandidate, draftName, draftDescription, sampleQuery, promotionNote, evalEnforcement, approvalActor, savingEnforcement, selectedProfiles, candidateRetrievalConfig, tuningControls, liveSelected, liveResolved, liveRetrievalConfig, approvedLiveEmbeddingName, effectiveSelectedProfiles, isPreparedCurrent, hasUnsavedDraftChanges, selectedOptionLabels, queryTransformEnabled, expectedChange, comparisonTiles, cacheStats, cacheMetrics, activeCachePolicy, activeCacheVersion, cacheScopeCount, currentLiveSignature, liveHistoryVersions, inspectedHistoryVersion, setVisualMode, setSelectedProfiles, setTuningControls, setDraftName, setDraftDescription, setSampleQuery, setPromotionNote, setApprovalActor, setSelectedHistoryVersion, updateRetrievalToggle, updateRetrievalNumber, resetDraftForm, prepareSandboxCandidate, saveDraft, runCompare, runEvalPack, promoteCandidate, rollbackVersion, saveEvalEnforcement, scrollToVersionHistory, runOpsAction } = useTuningWorkspace();
  return (
    <>
      <section className="card tuning-lab-compare-shell">
              <div className="section-head">
                <div>
                  <h2>Test &amp; Compare</h2>
                  <p>Run the same query against live production and the governed sandbox candidate, while preserving ACL-safe retrieval and provenance.</p>
                </div>
              </div>
      
              <div className="tuning-lab-compare-input">
                <TextInput value={sampleQuery} onChange={(event) => setSampleQuery(event.target.value)} placeholder="e.g. How does the Q4 liability clause affect subcontracting?" />
                <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={runCompare} disabled={isComparing || isLoading}>
                  {isComparing ? "Running Compare..." : "Run Compare"}
                </button>
              </div>
      
              <div className="tuning-lab-shell-note">
                <MaterialIcon name="info" />
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
              <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={resetDraftForm}>
                Discard Candidate
              </button>
              <TextInput className="tuning-lab-promotion-note" value={promotionNote} onChange={(event) => setPromotionNote(event.target.value)} aria-label="Promotion note" />
              <Select
                aria-label="Promotion evaluation enforcement"
                value={evalEnforcement.override == null ? "" : String(evalEnforcement.override)}
                disabled={savingEnforcement}
                onChange={(event) => saveEvalEnforcement(event.target.value || null)}
              >
                <option value="">Default ({String(evalEnforcement.effective)} via {evalEnforcement.source})</option>
                <option value="require">Require passing eval</option>
                <option value="warn">Warn only</option>
              </Select>
              <TextInput className="tuning-lab-promotion-note" value={approvalActor} onChange={(event) => setApprovalActor(event.target.value)} aria-label="Approval actor" placeholder="Approval actor (production)" />
              <span className="tuning-lab-draft-state">
                {editingDraftId ? (hasUnsavedDraftChanges ? "Draft has unsaved changes" : "Draft saved") : "Save draft before promotion"}
              </span>
              <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={saveDraft} disabled={savingDraft || (Boolean(editingDraftId) && !hasUnsavedDraftChanges)}>
                {savingDraft ? "Saving Draft..." : editingDraftId ? "Update Draft" : "Save as Draft"}
              </button>
              <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={runEvalPack} disabled={isEvaluating || savingDraft || !editingDraftId}>
                {isEvaluating ? "Running Eval Pack..." : "Run Eval Pack"}
              </button>
              <span className="tuning-lab-draft-state">
                {evalRun
                  ? `Eval gate: ${String(evalRun.gate_status)} · recall@5 ${Number((evalRun.gate_aggregates as GenericMap)?.recall_at_5 ?? NaN).toFixed(3)} · MRR ${Number((evalRun.gate_aggregates as GenericMap)?.mrr ?? NaN).toFixed(3)}${(evalRun.deltas_vs_live_baseline as GenericMap) ? ` · vs live: recall@5 Δ ${formatMetricDelta((evalRun.deltas_vs_live_baseline as GenericMap)?.recall_at_5)} · MRR Δ ${formatMetricDelta((evalRun.deltas_vs_live_baseline as GenericMap)?.mrr)}` : ""}`
                  : `No eval evidence yet — mode is ${String(evalEnforcement.effective)}`}
              </span>
              <button
                type="button"
                className="stitch-button stitch-button-primary stitch-button-small"
                onClick={promoteCandidate}
                disabled={isPromoting || savingDraft || (String(evalEnforcement.effective) === "require" && (evalRun ? evalRun.gate_status !== "pass" : true))}
              >
                {isPromoting ? "Promoting..." : evalRun && evalRun.gate_status !== "pass" ? "Eval Gate Failed" : "Promote to Live"}
              </button>
            </footer>
    </>
  );
}
