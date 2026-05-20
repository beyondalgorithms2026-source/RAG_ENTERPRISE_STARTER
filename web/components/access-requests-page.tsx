"use client";

import { useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type AccessRequest = {
  id: number;
  status: string;
  question: string;
  business_reason: string;
  source_hint?: string | null;
  metadata_json?: {
    suggested_approver_email?: string | null;
    suggested_approver_display_name?: string | null;
    requester_comment?: string | null;
    approver_return?: {
      decision?: string | null;
      decision_reason?: string | null;
      alternate_business_approver?: {
        contact_email?: string | null;
        contact_display_name?: string | null;
      } | null;
    } | null;
  } | null;
  approved_duration_hours?: number | null;
  expires_at?: string | null;
  created_at?: string | null;
  routing?: {
    business_approver_display_name?: string | null;
    business_approver_email?: string | null;
  } | null;
  targets: { source_id: number }[];
};

type ApprovalItem = {
  id: number;
  access_request_id: number;
  status: string;
  decision?: string | null;
  decision_reason?: string | null;
  request_payload_json: Record<string, unknown>;
  resolution_payload_json: Record<string, unknown>;
  created_at?: string | null;
};

type NotificationItem = {
  id: number;
  access_request_id?: number | null;
  event_type: string;
  title: string;
  body: string;
  status: string;
  created_at?: string | null;
};

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function formatTime(value?: string | null) {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function AccessRequestsPage() {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [feedback, setFeedback] = useState("");
  const [decisionReasons, setDecisionReasons] = useState<Record<number, string>>({});
  const [sourceIdDrafts, setSourceIdDrafts] = useState<Record<number, string>>({});
  const [alternateApproverEmailDrafts, setAlternateApproverEmailDrafts] = useState<Record<number, string>>({});
  const [alternateApproverNameDrafts, setAlternateApproverNameDrafts] = useState<Record<number, string>>({});

  async function refresh() {
    const [requestPayload, approvalPayload, notificationPayload] = await Promise.all([
      browserFetch<{ access_requests: AccessRequest[] }>("/access-requests"),
      browserFetch<{ approvals: ApprovalItem[] }>("/me/approvals"),
      browserFetch<{ notifications: NotificationItem[] }>("/me/notifications"),
    ]);
    setRequests(requestPayload.access_requests);
    setApprovals(approvalPayload.approvals);
    setNotifications(notificationPayload.notifications);
  }

  useEffect(() => {
    refresh().catch((err) => setFeedback(err instanceof Error ? err.message : "Failed to load access state."));
  }, []);

  const pendingApprovals = useMemo(() => approvals.filter((item) => item.status === "pending"), [approvals]);
  const unreadNotifications = useMemo(() => notifications.filter((item) => item.status !== "read"), [notifications]);

  async function decideApproval(inboxId: number, decision: "approve_24h" | "approve_7d" | "approve_30d" | "deny" | "return_not_owner" | "return_not_relevant" | "return_reroute") {
    try {
      await browserFetch(`/me/approvals/${inboxId}/decision`, {
        method: "POST",
        json: {
          decision,
          decision_reason:
            decisionReasons[inboxId]
            || (decision === "deny"
              ? "Denied."
              : decision.startsWith("return_")
                ? "Returned to admin for rerouting or clarification."
                : "Approved for temporary access."),
          selected_source_ids: (sourceIdDrafts[inboxId] || "")
            .split(",")
            .map((value) => Number(value.trim()))
            .filter((value) => Number.isFinite(value) && value > 0),
          alternate_business_approver_email: alternateApproverEmailDrafts[inboxId] || undefined,
          alternate_business_approver_display_name: alternateApproverNameDrafts[inboxId] || undefined,
        },
      });
      setFeedback(`Approval ${decision.replace("_", " ")} recorded.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not record approval.");
    }
  }

  async function markRead(notificationId: number) {
    try {
      await browserFetch(`/me/notifications/${notificationId}/read`, { method: "POST" });
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not mark notification as read.");
    }
  }

  return (
    <div className="history-page">
      <div className="history-header">
        <div>
          <h1>Approvals &amp; Access</h1>
          <p>Track your access requests, review routed approval tasks, and keep up with temporary-access notifications.</p>
        </div>
        <div className="history-thread-meta">
          <span>{pendingApprovals.length} pending approval{pendingApprovals.length === 1 ? "" : "s"}</span>
          <span>{unreadNotifications.length} unread notification{unreadNotifications.length === 1 ? "" : "s"}</span>
        </div>
      </div>

      {feedback ? <div className="chat-error-banner">{feedback}</div> : null}

      <section className="history-list">
        <div className="history-empty-card">
          <span className="material-symbols-outlined">approval</span>
          <strong>My Access Requests</strong>
          <p>Requests are created from access-limited answer states in Chat and stay here until routed, denied, or granted.</p>
        </div>
        {requests.length === 0 ? (
          <div className="history-empty-card">
            <span className="material-symbols-outlined">lock</span>
            <strong>No access requests yet.</strong>
            <p>When a question needs more visibility than your current access allows, the request flow will appear directly in Chat.</p>
          </div>
        ) : (
          requests.map((request) => (
            <article key={request.id} className="history-thread-card">
              <div className="history-thread-head">
                <span className="material-symbols-outlined">shield_lock</span>
                <div>
                  <strong>Request #{request.id} · {titleCase(request.status)}</strong>
                  <span>{formatTime(request.created_at)}</span>
                </div>
              </div>
              <p>{request.question}</p>
              <div className="history-thread-meta">
                <span>{request.source_hint || "No source hint provided"}</span>
                <span>{request.metadata_json?.suggested_approver_email ? `Suggested approver: ${request.metadata_json.suggested_approver_email}` : "No suggested approver"}</span>
                <span>{request.approved_duration_hours ? `${request.approved_duration_hours}h approved` : "Awaiting decision"}</span>
                <span>{request.expires_at ? `Expires ${formatTime(request.expires_at)}` : "No active expiry yet"}</span>
              </div>
              {request.metadata_json?.requester_comment ? <p>{request.metadata_json.requester_comment}</p> : null}
              {request.metadata_json?.approver_return ? (
                <div className="history-empty-actions">
                  <span>{titleCase(String(request.metadata_json.approver_return.decision || "returned"))}</span>
                  <span>{String(request.metadata_json.approver_return.decision_reason || "Returned to admin")}</span>
                </div>
              ) : null}
            </article>
          ))
        )}
      </section>

      <section className="history-list">
        <div className="history-empty-card">
          <span className="material-symbols-outlined">move_to_inbox</span>
          <strong>My Routed Approvals</strong>
          <p>If you are the designated business approver for a protected source, review the request here and choose a temporary duration.</p>
        </div>
        {approvals.length === 0 ? (
          <div className="history-empty-card">
            <span className="material-symbols-outlined">inbox</span>
            <strong>No approval tasks assigned.</strong>
            <p>Routed business approvals will appear here without needing the admin console.</p>
          </div>
        ) : (
          approvals.map((approval) => (
            <article key={approval.id} className="history-thread-card">
              <div className="history-thread-head">
                <span className="material-symbols-outlined">assignment</span>
                <div>
                  <strong>Approval #{approval.id} · Request #{approval.access_request_id}</strong>
                  <span>{titleCase(approval.status)} · {formatTime(approval.created_at)}</span>
                </div>
              </div>
              <p>Mapped sources: {Array.isArray(approval.request_payload_json.source_ids) ? (approval.request_payload_json.source_ids as number[]).join(", ") : "Pending mapping"}</p>
              <p>Business reason: {String(approval.request_payload_json.business_reason || "No reason provided")}</p>
              <p>{String(approval.request_payload_json.admin_note || "No admin note provided")}</p>
              <input
                value={sourceIdDrafts[approval.id] || (Array.isArray(approval.request_payload_json.source_ids) ? (approval.request_payload_json.source_ids as number[]).join(", ") : "")}
                onChange={(event) => setSourceIdDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                placeholder="Protected source ids to approve, comma separated"
              />
              <textarea
                rows={2}
                value={decisionReasons[approval.id] || ""}
                onChange={(event) => setDecisionReasons((current) => ({ ...current, [approval.id]: event.target.value }))}
                placeholder="Business approval reason"
              />
              <input
                value={alternateApproverEmailDrafts[approval.id] || ""}
                onChange={(event) => setAlternateApproverEmailDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                placeholder="Alternate approver email if returning for reroute"
              />
              <input
                value={alternateApproverNameDrafts[approval.id] || ""}
                onChange={(event) => setAlternateApproverNameDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                placeholder="Alternate approver name"
              />
              <div className="history-empty-actions">
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "approve_24h")}>Approve 24h</button>
                <button type="button" className="stitch-button stitch-button-primary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "approve_7d")}>Approve 7d</button>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "approve_30d")}>Approve 30d</button>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "return_not_owner")}>Not My Data</button>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "return_not_relevant")}>Doesn&apos;t Concern Me</button>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "return_reroute")}>Suggest Alternate</button>
                <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={approval.status !== "pending"} onClick={() => decideApproval(approval.id, "deny")}>Deny</button>
              </div>
            </article>
          ))
        )}
      </section>

      <section className="history-list">
        <div className="history-empty-card">
          <span className="material-symbols-outlined">notifications</span>
          <strong>Notifications</strong>
          <p>In-app notifications are the source of truth in M16.1. Email-ready payloads are stored on the backend for later delivery wiring.</p>
        </div>
        {notifications.length === 0 ? (
          <div className="history-empty-card">
            <span className="material-symbols-outlined">notifications_off</span>
            <strong>No notifications yet.</strong>
            <p>Request routing, approvals, grants, and expiries will appear here.</p>
          </div>
        ) : (
          notifications.map((item) => (
            <article key={item.id} className="history-thread-card">
              <div className="history-thread-head">
                <span className="material-symbols-outlined">{item.status === "read" ? "draft" : "mark_email_unread"}</span>
                <div>
                  <strong>{item.title}</strong>
                  <span>{formatTime(item.created_at)}</span>
                </div>
              </div>
              <p>{item.body}</p>
              <div className="history-empty-actions">
                <span>{titleCase(item.event_type)}</span>
                {item.status !== "read" ? (
                  <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => markRead(item.id)}>
                    Mark Read
                  </button>
                ) : null}
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
