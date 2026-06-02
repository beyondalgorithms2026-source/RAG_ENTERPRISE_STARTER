"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

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
  created_at?: string | null;
};

type AdminPayload = {
  approvals: Approval[];
  feedback: FeedbackRow[];
  negative_feedback: NegativeFeedbackRow[];
  negative_feedback_reason_counts: { negative_reason: string; count: number; latest_at?: string | null }[];
  top_failed_queries: { question: string; count: number; latest_at?: string | null }[];
  invocations: ToolInvocation[];
};

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function AdminActionsPanel() {
  const [payload, setPayload] = useState<AdminPayload>({
    approvals: [],
    feedback: [],
    negative_feedback: [],
    negative_feedback_reason_counts: [],
    top_failed_queries: [],
    invocations: [],
  });
  const [feedback, setFeedback] = useState("");
  const [reviewReasons, setReviewReasons] = useState<Record<number, string>>({});
  const [toolDraft, setToolDraft] = useState({
    tool_name: "generate_report",
    corpus_name: "default",
    payload: '{"artifact_type":"csv","title":"Manual test report"}',
  });

  async function refresh() {
    const [approvalsPayload, feedbackPayload, toolsPayload] = await Promise.all([
      browserFetch<{ approvals: Approval[] }>("/admin/approvals"),
      browserFetch<{
        feedback: FeedbackRow[];
        negative_feedback: NegativeFeedbackRow[];
        negative_feedback_reason_counts: AdminPayload["negative_feedback_reason_counts"];
        top_failed_queries: AdminPayload["top_failed_queries"];
      }>("/admin/feedback"),
      browserFetch<{ invocations: ToolInvocation[] }>("/admin/tools"),
    ]);
    setPayload({
      approvals: approvalsPayload.approvals,
      feedback: feedbackPayload.feedback,
      negative_feedback: feedbackPayload.negative_feedback || [],
      negative_feedback_reason_counts: feedbackPayload.negative_feedback_reason_counts || [],
      top_failed_queries: feedbackPayload.top_failed_queries,
      invocations: toolsPayload.invocations,
    });
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
          <label><span>Tool</span><select value={toolDraft.tool_name} onChange={(event) => setToolDraft((current) => ({ ...current, tool_name: event.target.value }))}><option value="generate_report">generate_report</option><option value="send_email">send_email</option><option value="send_slack">send_slack</option><option value="create_calendar_event">create_calendar_event</option></select></label>
          <label><span>Corpus</span><input value={toolDraft.corpus_name} onChange={(event) => setToolDraft((current) => ({ ...current, corpus_name: event.target.value }))} /></label>
          <label className="form-span-3"><span>Payload JSON</span><textarea value={toolDraft.payload} rows={4} onChange={(event) => setToolDraft((current) => ({ ...current, payload: event.target.value }))} /></label>
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
              <textarea value={reviewReasons[approval.id] || ""} rows={2} onChange={(event) => setReviewReasons((current) => ({ ...current, [approval.id]: event.target.value }))} placeholder="Review reason" />
            </article>
          ))}
        </div>
      </section>

      <section className="admin-card page-stack">
        <h2>Top Failed Queries</h2>
        {payload.top_failed_queries.length === 0 ? <p className="empty-copy">No failed query feedback yet.</p> : null}
        <div className="admin-list">
          {payload.top_failed_queries.map((item) => (
            <article key={item.question} className="admin-list-item">
              <div><strong>{item.question}</strong><p>{item.count} report(s) · latest {item.latest_at || "unknown"}</p></div>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-card page-stack">
        <h2>Structured Answer Failures</h2>
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
        <div className="admin-list">
          {payload.negative_feedback.map((item) => (
            <article key={item.id} className="admin-list-item admin-list-item-stacked">
              <div className="admin-list-main">
                <div>
                  <strong>#{item.id} {titleCase(item.negative_reason)}</strong>
                  <p>{item.question}</p>
                  <small>{item.actor_email || "unknown actor"} · {item.used_chunks_count} chunk(s) · {item.citations_json.length} citation(s) · {item.created_at}</small>
                </div>
              </div>
              <p>{item.answer_text ? `${item.answer_text.slice(0, 260)}${item.answer_text.length > 260 ? "..." : ""}` : "No answer text captured."}</p>
              {item.note ? <small>Note: {item.note}</small> : null}
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
