"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";

type Approval = {
  id: number;
  approval_type: string;
  status: string;
  reason: string;
  requester_email?: string | null;
  requested_payload_json: Record<string, unknown>;
  response_payload_json: Record<string, unknown>;
  review_reason?: string | null;
  created_at?: string | null;
};

type ToolInvocation = {
  id: number;
  tool_name: string;
  status: string;
  corpus_name?: string | null;
  actor_email?: string | null;
  denial_reason?: string | null;
  approval_request_id?: number | null;
  created_at?: string | null;
};

type FeedbackRow = {
  id: number;
  question: string;
  feedback_type: string;
  rating?: string | null;
  reason: string;
  suggested_source?: string | null;
  actor_email?: string | null;
  created_at?: string | null;
};

type NegativeFeedbackRow = {
  id: number;
  question: string;
  answer_text: string;
  negative_reason: string;
  note: string;
  used_chunks_count: number;
  actor_email?: string | null;
  citations_json: Record<string, unknown>[];
  cited_source_ids_json: number[];
  cited_chunk_ids_json: number[];
  active_profile_snapshot_json?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  request_id?: string | null;
  answer_path?: string | null;
  created_at?: string | null;
};

type FailureCluster = {
  id: number;
  label: string;
  status: string;
  query_count: number;
  sample_questions_json: string[];
  annotation_json?: Record<string, unknown>;
  updated_at?: string | null;
};

type AdminPayload = {
  approvals: Approval[];
  feedback: FeedbackRow[];
  negative_feedback: NegativeFeedbackRow[];
  negative_feedback_reason_counts: { negative_reason: string; count: number; latest_at?: string | null }[];
  top_failed_queries: { question: string; count: number; latest_at?: string | null }[];
  invocations: ToolInvocation[];
  clusters: FailureCluster[];
  eval_packs: Record<string, unknown>[];
};

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function preview(value: string, maxLength = 260) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

export function AdminActionsPanel() {
  const [payload, setPayload] = useState<AdminPayload>({
    approvals: [],
    feedback: [],
    negative_feedback: [],
    negative_feedback_reason_counts: [],
    top_failed_queries: [],
    invocations: [],
    clusters: [],
    eval_packs: [],
  });
  const [feedback, setFeedback] = useState("");
  const [selectedFailure, setSelectedFailure] = useState<NegativeFeedbackRow | null>(null);
  const [reviewReasons, setReviewReasons] = useState<Record<number, string>>({});
  const [toolDraft, setToolDraft] = useState({
    tool_name: "generate_report",
    corpus_name: "default",
    payload: '{"artifact_type":"csv","title":"Manual test report"}',
  });

  async function refresh() {
    const emptyQueryMining = { clusters: [], derived_eval_packs: [], eval_packs: [] };
    const [approvalsPayload, feedbackPayload, toolsPayload, queryMiningPayload] = await Promise.all([
      browserFetch<{ approvals: Approval[] }>("/admin/approvals"),
      browserFetch<{
        feedback: FeedbackRow[];
        negative_feedback: NegativeFeedbackRow[];
        negative_feedback_reason_counts: AdminPayload["negative_feedback_reason_counts"];
        top_failed_queries: AdminPayload["top_failed_queries"];
      }>("/admin/feedback"),
      browserFetch<{ invocations: ToolInvocation[] }>("/admin/tools"),
      browserFetch<{ clusters?: FailureCluster[]; derived_eval_packs?: Record<string, unknown>[]; eval_packs?: Record<string, unknown>[] }>("/admin/query-mining").catch(() => emptyQueryMining),
    ]);
    setPayload({
      approvals: approvalsPayload.approvals,
      feedback: feedbackPayload.feedback,
      negative_feedback: feedbackPayload.negative_feedback || [],
      negative_feedback_reason_counts: feedbackPayload.negative_feedback_reason_counts || [],
      top_failed_queries: feedbackPayload.top_failed_queries,
      invocations: toolsPayload.invocations,
      clusters: queryMiningPayload.clusters || [],
      eval_packs: queryMiningPayload.derived_eval_packs || queryMiningPayload.eval_packs || [],
    });
    setSelectedFailure((current) => current ? (feedbackPayload.negative_feedback || []).find((item) => item.id === current.id) || current : (feedbackPayload.negative_feedback || [])[0] || null);
  }

  useEffect(() => {
    refresh().catch((err) => setFeedback(err instanceof Error ? err.message : "Failed to load workflow state."));
  }, []);

  async function reviewApproval(approvalId: number, status: "approved" | "denied") {
    try {
      await browserFetch(`/admin/approvals/${approvalId}/review`, {
        method: "POST",
        json: { status, review_reason: reviewReasons[approvalId] || (status === "approved" ? "Approved." : "Denied.") },
      });
      setFeedback(`Approval ${approvalId} ${status}.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Review failed.");
    }
  }

  async function invokeTool() {
    try {
      const result = await browserFetch<{ status: string; invocation_id: number; denial_reason?: string | null; approval_request_id?: number | null }>("/tools/invoke", {
        method: "POST",
        json: {
          tool_name: toolDraft.tool_name,
          corpus_name: toolDraft.corpus_name,
          payload: JSON.parse(toolDraft.payload || "{}"),
        },
      });
      setFeedback(`Tool ${result.status}. Invocation ${result.invocation_id}${result.approval_request_id ? `, approval ${result.approval_request_id}` : ""}${result.denial_reason ? `, ${result.denial_reason}` : ""}.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Tool invocation failed.");
    }
  }

  function openInTuningLab(question: string, label?: string) {
    window.localStorage.setItem("rag:tuningSeedQuestion", question);
    if (label) {
      window.localStorage.setItem("rag:tuningSeedLabel", label);
    }
    window.location.assign("/console/admin/profiles");
  }

  async function buildClusters() {
    try {
      const result = await browserFetch<{ clusters: FailureCluster[] }>("/admin/query-mining/clusters/build", { method: "POST" });
      setFeedback(`Built ${result.clusters.length} failure cluster(s).`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Cluster build failed.");
    }
  }

  async function createEvalPack(cluster: FailureCluster) {
    try {
      const name = `feedback-cluster-${cluster.id}-${Date.now()}`;
      await browserFetch("/admin/query-mining/eval-packs", {
        method: "POST",
        json: { name, cluster_ids: [cluster.id] },
      });
      setFeedback(`Created eval pack ${name}.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Eval-pack creation failed.");
    }
  }

  return (
    <div className="admin-page page-stack">
      <section className="admin-section-intro">
        <span>Actions</span>
        <h1>Tools, Approvals, Feedback</h1>
        <p>Run governed tool actions, review sensitive outputs, and inspect missing-evidence feedback loops.</p>
      </section>

      <section className="admin-card page-stack">
        <h2>Tool Invocation</h2>
        <div className="admin-form-grid">
          <label><span>Tool</span><Select value={toolDraft.tool_name} onChange={(event) => setToolDraft((current) => ({ ...current, tool_name: event.target.value }))}><option value="generate_report">generate_report</option><option value="send_email">send_email</option><option value="send_slack">send_slack</option><option value="create_calendar_event">create_calendar_event</option></Select></label>
          <label><span>Corpus</span><TextInput value={toolDraft.corpus_name} onChange={(event) => setToolDraft((current) => ({ ...current, corpus_name: event.target.value }))} /></label>
          <label className="form-span-3"><span>Payload JSON</span><Textarea value={toolDraft.payload} rows={4} onChange={(event) => setToolDraft((current) => ({ ...current, payload: event.target.value }))} /></label>
        </div>
        <div className="toolbar-inline">
          <button type="button" className="stitch-button stitch-button-primary" onClick={invokeTool}>Invoke Tool</button>
          {feedback ? <strong className="sources-upload-status">{feedback}</strong> : null}
        </div>
      </section>

      <section className="admin-card page-stack">
        <h2>Approval Queue</h2>
        {payload.approvals.length === 0 ? <p className="empty-copy">No approvals yet.</p> : null}
        <div className="admin-list">
          {payload.approvals.map((approval) => (
            <article key={approval.id} className="admin-list-item admin-list-item-stacked">
              <div className="admin-list-main">
                <div>
                  <strong>#{approval.id} {titleCase(approval.approval_type)}</strong>
                  <p>{approval.reason || "No reason supplied."}</p>
                  <small>{approval.requester_email || "unknown requester"} · {titleCase(approval.status)} · {approval.created_at}</small>
                </div>
                <div className="toolbar-inline">
                  <button type="button" className="stitch-button stitch-button-primary" disabled={approval.status !== "pending"} onClick={() => reviewApproval(approval.id, "approved")}>Approve</button>
                  <button type="button" className="stitch-button stitch-button-secondary" disabled={approval.status !== "pending"} onClick={() => reviewApproval(approval.id, "denied")}>Deny</button>
                </div>
              </div>
              <Textarea value={reviewReasons[approval.id] || ""} rows={2} onChange={(event) => setReviewReasons((current) => ({ ...current, [approval.id]: event.target.value }))} placeholder="Review reason" />
            </article>
          ))}
        </div>
      </section>

      <section className="admin-card page-stack">
        <div className="section-head">
          <div>
            <h2>Top Failed Queries</h2>
            <p>Use repeated failed questions as candidate prompts for sandbox tuning and derived eval packs.</p>
          </div>
          <button type="button" className="stitch-button stitch-button-secondary" onClick={buildClusters}>Build Clusters</button>
        </div>
        {payload.top_failed_queries.length === 0 ? <p className="empty-copy">No failed query feedback yet.</p> : null}
        <div className="admin-list">
          {payload.top_failed_queries.map((item) => (
            <article key={item.question} className="admin-list-item">
              <div><strong>{item.question}</strong><p>{item.count} report(s) · latest {item.latest_at || "unknown"}</p></div>
              <div className="toolbar-inline">
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => openInTuningLab(item.question, "Failed query")}>Run In Sandbox</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-card page-stack">
        <div className="section-head">
          <div>
            <h2>Structured Answer Failures</h2>
            <p>Inspect thumbs-down context, citations, and active profiles before deciding what to tune.</p>
          </div>
        </div>
        {payload.negative_feedback_reason_counts.length === 0 ? <p className="empty-copy">No structured answer-failure feedback yet.</p> : null}
        {payload.negative_feedback_reason_counts.length ? (
          <div className="metric-grid compact-grid">
            {payload.negative_feedback_reason_counts.map((item) => (
              <div key={item.negative_reason} className="metric-card">
                <span>{titleCase(item.negative_reason)}</span>
                <strong>{item.count}</strong>
                <small>latest {item.latest_at || "unknown"}</small>
              </div>
            ))}
          </div>
        ) : null}
        <div className="feedback-workbench-grid">
          <div className="admin-list">
            {payload.negative_feedback.map((item) => (
              <article key={item.id} className={`admin-list-item admin-list-item-stacked feedback-review-item ${selectedFailure?.id === item.id ? "is-selected" : ""}`} onClick={() => setSelectedFailure(item)}>
                <div className="admin-list-main">
                  <div>
                    <strong>#{item.id} {titleCase(item.negative_reason)}</strong>
                    <p>{item.question}</p>
                    <small>{item.actor_email || "unknown actor"} · {item.used_chunks_count} chunk(s) · {item.citations_json.length} citation(s) · {item.created_at}</small>
                  </div>
                </div>
                <p>{item.answer_text ? preview(item.answer_text) : "No answer text captured."}</p>
                {item.note ? <small>Note: {item.note}</small> : null}
              </article>
            ))}
          </div>
          <aside className="feedback-detail-panel">
            {selectedFailure ? (
              <>
                <div className="feedback-detail-head">
                  <div>
                    <span>Selected Failure</span>
                    <strong>{titleCase(selectedFailure.negative_reason)}</strong>
                  </div>
                  <button type="button" className="stitch-button stitch-button-primary" onClick={() => openInTuningLab(selectedFailure.question, `Feedback #${selectedFailure.id}`)}>Run In Sandbox</button>
                </div>
                <section>
                  <span>Question</span>
                  <p>{selectedFailure.question}</p>
                </section>
                <section>
                  <span>Failed Answer</span>
                  <p>{selectedFailure.answer_text || "No answer text captured."}</p>
                </section>
                {selectedFailure.note ? (
                  <section>
                    <span>User Note</span>
                    <p>{selectedFailure.note}</p>
                  </section>
                ) : null}
                <div className="feedback-context-grid">
                  <article><span>Chunks</span><strong>{selectedFailure.used_chunks_count}</strong></article>
                  <article><span>Citations</span><strong>{selectedFailure.citations_json.length}</strong></article>
                  <article><span>Answer Path</span><strong>{selectedFailure.answer_path || "unknown"}</strong></article>
                </div>
                <section>
                  <span>Cited Source IDs</span>
                  <p>{selectedFailure.cited_source_ids_json.length ? selectedFailure.cited_source_ids_json.join(", ") : "None captured"}</p>
                </section>
                <section>
                  <span>Cited Chunk IDs</span>
                  <p>{selectedFailure.cited_chunk_ids_json.length ? selectedFailure.cited_chunk_ids_json.join(", ") : "None captured"}</p>
                </section>
                <section>
                  <span>Active Profile Snapshot</span>
                  <pre>{JSON.stringify(selectedFailure.active_profile_snapshot_json || {}, null, 2)}</pre>
                </section>
              </>
            ) : (
              <p className="empty-copy">Select a structured failure to inspect the tuning context.</p>
            )}
          </aside>
        </div>
      </section>

      <section className="admin-card page-stack">
        <div className="section-head">
          <div>
            <h2>Failure Clusters For Tuning</h2>
            <p>Clusters group repeated weak-answer patterns so admins can create eval packs before promoting candidate profiles.</p>
          </div>
          <button type="button" className="stitch-button stitch-button-secondary" onClick={buildClusters}>Refresh Clusters</button>
        </div>
        {payload.clusters.length === 0 ? <p className="empty-copy">No clusters yet. Build clusters after feedback is captured.</p> : null}
        <div className="feedback-cluster-grid">
          {payload.clusters.map((cluster) => (
            <article key={cluster.id} className="feedback-cluster-card">
              <span>{titleCase(cluster.status || "open")}</span>
              <strong>{cluster.label}</strong>
              <p>{cluster.query_count} query event(s) · updated {cluster.updated_at || "unknown"}</p>
              <div className="feedback-cluster-samples">
                {(cluster.sample_questions_json || []).slice(0, 3).map((question) => (
                  <button key={question} type="button" onClick={() => openInTuningLab(question, `Cluster #${cluster.id}`)}>{question}</button>
                ))}
              </div>
              <div className="toolbar-inline">
                <button type="button" className="stitch-button stitch-button-secondary" onClick={() => createEvalPack(cluster)}>Create Eval Pack</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-card page-stack">
        <h2>Recent Tool Invocations</h2>
        <div className="admin-list">
          {payload.invocations.map((item) => (
            <article key={item.id} className="admin-list-item">
              <div>
                <strong>{item.tool_name}</strong>
                <p>{titleCase(item.status)} · {item.corpus_name || "default"} · {item.actor_email || "unknown actor"}</p>
                {item.denial_reason ? <small>{item.denial_reason}</small> : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
