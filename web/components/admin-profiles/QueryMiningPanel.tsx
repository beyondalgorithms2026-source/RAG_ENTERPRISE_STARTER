"use client";

import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";
import {
  EmptyState, ParameterLabel, TUNING_PROFILE_TYPES, candidateRetrievalSummary,
  evalEvidenceSummary, formatMetricDelta, formatTimestamp, profileTypeLabel,
  renderCompareAnswer, selectedProfilesSignature, transformSummaryText,
  useTuningWorkspace, versionModelDetail, versionProfileConfig, versionProfileName,
} from "./tuning-workspace-context";

export function QueryMiningPanel() {
  const { historySectionRef, tuningPayload, comparePayload, error, isLoading, isComparing, savingDraft, isPromoting, isRollingBack, isEvaluating, evalRun, isOpsBusy, editingDraftId, tuningHistory, tuningOps, retrievalEvidence, visualMode, preparedCandidate, draftName, draftDescription, sampleQuery, promotionNote, evalEnforcement, approvalActor, savingEnforcement, selectedProfiles, candidateRetrievalConfig, tuningControls, liveSelected, liveResolved, liveRetrievalConfig, approvedLiveEmbeddingName, effectiveSelectedProfiles, isPreparedCurrent, hasUnsavedDraftChanges, selectedOptionLabels, queryTransformEnabled, expectedChange, comparisonTiles, cacheStats, cacheMetrics, activeCachePolicy, activeCacheVersion, cacheScopeCount, currentLiveSignature, liveHistoryVersions, inspectedHistoryVersion, setVisualMode, setSelectedProfiles, setTuningControls, setDraftName, setDraftDescription, setSampleQuery, setPromotionNote, setApprovalActor, setSelectedHistoryVersion, updateRetrievalToggle, updateRetrievalNumber, resetDraftForm, prepareSandboxCandidate, saveDraft, runCompare, runEvalPack, promoteCandidate, rollbackVersion, saveEvalEnforcement, scrollToVersionHistory, runOpsAction } = useTuningWorkspace();
  return (
    <>
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
                  <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={isOpsBusy !== ""} onClick={() => runOpsAction("build-clusters")}>
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
    </>
  );
}
