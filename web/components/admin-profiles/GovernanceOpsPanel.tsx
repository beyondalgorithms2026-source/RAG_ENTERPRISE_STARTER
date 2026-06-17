"use client";

import Link from "next/link";

import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";
import {
  EmptyState, ParameterLabel, TUNING_PROFILE_TYPES, candidateRetrievalSummary, type GenericMap,
  evalEvidenceSummary, formatMetricDelta, formatTimestamp, profileTypeLabel,
  renderCompareAnswer, selectedProfilesSignature, transformSummaryText,
  useTuningWorkspace, versionModelDetail, versionProfileConfig, versionProfileName,
} from "./tuning-workspace-context";

export function GovernanceOpsPanel() {
  const { historySectionRef, tuningPayload, comparePayload, error, isLoading, isComparing, savingDraft, isPromoting, isRollingBack, isEvaluating, evalRun, isOpsBusy, editingDraftId, tuningHistory, tuningOps, retrievalEvidence, visualMode, preparedCandidate, draftName, draftDescription, sampleQuery, promotionNote, evalEnforcement, approvalActor, savingEnforcement, selectedProfiles, candidateRetrievalConfig, tuningControls, liveSelected, liveResolved, liveRetrievalConfig, approvedLiveEmbeddingName, effectiveSelectedProfiles, isPreparedCurrent, hasUnsavedDraftChanges, selectedOptionLabels, queryTransformEnabled, expectedChange, comparisonTiles, cacheStats, cacheMetrics, activeCachePolicy, activeCacheVersion, cacheScopeCount, currentLiveSignature, liveHistoryVersions, inspectedHistoryVersion, setVisualMode, setSelectedProfiles, setTuningControls, setDraftName, setDraftDescription, setSampleQuery, setPromotionNote, setApprovalActor, setSelectedHistoryVersion, updateRetrievalToggle, updateRetrievalNumber, resetDraftForm, prepareSandboxCandidate, saveDraft, runCompare, runEvalPack, promoteCandidate, rollbackVersion, saveEvalEnforcement, scrollToVersionHistory, runOpsAction } = useTuningWorkspace();
  return (
    <>
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
                      <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={(event) => { event.stopPropagation(); rollbackVersion(String(version.version_label)); }} disabled={isRollingBack || matchesCurrentProduction}>
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
                <Link className="stitch-button stitch-button-primary stitch-button-small" href="/console/admin/profiles/cache-policy">Manage Cache Policy</Link>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={isOpsBusy !== "" || !activeCachePolicy} onClick={() => runOpsAction("clear-cache")}>
                  {isOpsBusy === "clear-cache" ? "Clearing..." : "Clear Active Entries"}
                </button>
              </div>
            </section>
    </>
  );
}
