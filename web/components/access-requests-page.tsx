"use client";

import { MaterialIcon } from "@/components/icons";
import { useEffect, useMemo, useState } from "react";

import { Field } from "@/components/ui/Field";
import { TextInput } from "@/components/ui/TextInput";
import { Textarea } from "@/components/ui/Textarea";
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
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function requestStatusChip(status: string) {
  const value = status.toLowerCase();
  if (value.includes("grant") || value.includes("approv")) return "is-pass";
  if (value.includes("den") || value.includes("expir") || value.includes("reject")) return "is-fail";
  return "is-review";
}

function eventGlyph(eventType: string) {
  const value = eventType.toLowerCase();
  if (value.includes("grant") || value.includes("approve")) return "check";
  if (value.includes("deny") || value.includes("expir")) return "warning";
  if (value.includes("route")) return "swap_horiz";
  return "notifications";
}

/**
 * Approval gate: the inspectable-automation surface. Three lanes — reviews
 * assigned to the viewer (with reviewer note + timed-grant decisions), the
 * viewer's own access requests (with decision state), and the timestamped
 * workflow event feed. All lanes are live backend state.
 */
export function AccessRequestsPage() {
  const [requests, setRequests] = useState<AccessRequest[] | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[] | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [feedback, setFeedback] = useState("");
  const [loadError, setLoadError] = useState("");
  const [decisionReasons, setDecisionReasons] = useState<Record<number, string>>({});
  const [sourceIdDrafts, setSourceIdDrafts] = useState<Record<number, string>>({});
  const [alternateApproverEmailDrafts, setAlternateApproverEmailDrafts] = useState<Record<number, string>>({});
  const [alternateApproverNameDrafts, setAlternateApproverNameDrafts] = useState<Record<number, string>>({});
  const [returnOptionsOpen, setReturnOptionsOpen] = useState<Record<number, boolean>>({});

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
    refresh().catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load access state."));
  }, []);

  const pendingApprovals = useMemo(() => (approvals ?? []).filter((item) => item.status === "pending"), [approvals]);
  const resolvedApprovals = useMemo(() => (approvals ?? []).filter((item) => item.status !== "pending"), [approvals]);
  const unreadNotifications = useMemo(() => (notifications ?? []).filter((item) => item.status !== "read"), [notifications]);
  const loading = requests === null || approvals === null || notifications === null;

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
      setFeedback(`Decision "${decision.replace(/_/g, " ")}" recorded.`);
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
    <div className="v2-page">
      <header className="v2-page-head">
        <div>
          <p className="v2-kicker">Approval gate</p>
          <h1>Access is granted by people, on the record.</h1>
          <p className="v2-page-sub">
            When retrieval needs more visibility than a user has, the request routes to a business approver.
            Every decision carries a reviewer note, a time-boxed grant, and a timestamped event trail.
          </p>
        </div>
        <div className="v2-chip-row">
          <span className={`v2-status-chip ${pendingApprovals.length ? "is-review" : "is-pass"}`}>
            <MaterialIcon name="approval" />
            {pendingApprovals.length} pending review{pendingApprovals.length === 1 ? "" : "s"}
          </span>
          <span className={`v2-status-chip ${unreadNotifications.length ? "is-review" : "is-pass"}`}>
            <MaterialIcon name="notifications" />
            {unreadNotifications.length} unread event{unreadNotifications.length === 1 ? "" : "s"}
          </span>
        </div>
      </header>

      {loadError ? <div className="chat-error-banner" role="alert">{loadError}</div> : null}
      {feedback ? <div className="v2-flash" role="status">{feedback}</div> : null}

      {loading && !loadError ? (
        <div className="v2-empty" role="status">
          <MaterialIcon name="progress_activity" className="spin" />
          <strong>Loading approval state...</strong>
        </div>
      ) : null}

      {!loading ? (
        <>
          <section className="v2-panel" aria-label="Reviews waiting on you">
            <header className="v2-panel-head">
              <h2>Reviews waiting on you</h2>
              <span className="v2-row-note">Routed to you as business approver</span>
            </header>
            {pendingApprovals.length === 0 ? (
              <div className="v2-empty">
                <MaterialIcon name="inbox" />
                <strong>Nothing to review.</strong>
                <p>Requests routed to you as the responsible business approver will appear here with full context.</p>
              </div>
            ) : (
              pendingApprovals.map((approval) => {
                const sourceIds = Array.isArray(approval.request_payload_json.source_ids)
                  ? (approval.request_payload_json.source_ids as number[]).join(", ")
                  : "";
                const showReturn = returnOptionsOpen[approval.id] ?? false;
                return (
                  <article key={approval.id} className="v2-review-card">
                    <div className="v2-review-head">
                      <span className="v2-status-chip is-review">
                        <MaterialIcon name="schedule" />
                        Pending review
                      </span>
                      <span className="v2-review-id">Approval #{approval.id} · Request #{approval.access_request_id} · {formatTime(approval.created_at)}</span>
                    </div>
                    <dl className="v2-review-facts">
                      <div>
                        <dt>Business reason</dt>
                        <dd>{String(approval.request_payload_json.business_reason || "No reason provided")}</dd>
                      </div>
                      <div>
                        <dt>Admin note</dt>
                        <dd>{String(approval.request_payload_json.admin_note || "—")}</dd>
                      </div>
                      <div>
                        <dt>Mapped sources</dt>
                        <dd>{sourceIds || "Pending mapping"}</dd>
                      </div>
                    </dl>
                    <div className="v2-review-form">
                      <Field label="Reviewer note" help="Recorded on the decision and visible to the requester and admins.">
                        <Textarea
                          rows={2}
                          value={decisionReasons[approval.id] || ""}
                          onChange={(event) => setDecisionReasons((current) => ({ ...current, [approval.id]: event.target.value }))}
                          placeholder="Why this access is (or is not) appropriate..."
                        />
                      </Field>
                      <Field label="Protected source ids to approve" help="Comma separated; defaults to the mapped sources.">
                        <TextInput
                          value={sourceIdDrafts[approval.id] ?? sourceIds}
                          onChange={(event) => setSourceIdDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                          placeholder="e.g. 12, 47"
                        />
                      </Field>
                    </div>
                    <div className="v2-review-actions">
                      <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={() => decideApproval(approval.id, "approve_24h")}>Approve 24h</button>
                      <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "approve_7d")}>Approve 7d</button>
                      <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "approve_30d")}>Approve 30d</button>
                      <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "deny")}>Deny</button>
                      <button
                        type="button"
                        className="stitch-button stitch-button-secondary stitch-button-small"
                        aria-expanded={showReturn}
                        onClick={() => setReturnOptionsOpen((current) => ({ ...current, [approval.id]: !showReturn }))}
                      >
                        Return options {showReturn ? "−" : "+"}
                      </button>
                    </div>
                    {showReturn ? (
                      <div className="v2-review-return">
                        <div className="v2-review-form">
                          <Field label="Alternate approver email" help="Used when suggesting a reroute.">
                            <TextInput
                              value={alternateApproverEmailDrafts[approval.id] || ""}
                              onChange={(event) => setAlternateApproverEmailDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                              placeholder="owner@company.com"
                            />
                          </Field>
                          <Field label="Alternate approver name">
                            <TextInput
                              value={alternateApproverNameDrafts[approval.id] || ""}
                              onChange={(event) => setAlternateApproverNameDrafts((current) => ({ ...current, [approval.id]: event.target.value }))}
                              placeholder="Data owner"
                            />
                          </Field>
                        </div>
                        <div className="v2-review-actions">
                          <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "return_not_owner")}>Not my data</button>
                          <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "return_not_relevant")}>Doesn&apos;t concern me</button>
                          <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => decideApproval(approval.id, "return_reroute")}>Suggest alternate</button>
                        </div>
                      </div>
                    ) : null}
                  </article>
                );
              })
            )}
            {resolvedApprovals.length > 0 ? (
              <div className="v2-resolved-list">
                {resolvedApprovals.map((approval) => (
                  <article key={approval.id} className="v2-resolved-row">
                    <span className={`v2-status-chip ${requestStatusChip(String(approval.decision || approval.status))}`}>
                      <MaterialIcon name={requestStatusChip(String(approval.decision || approval.status)) === "is-pass" ? "check" : "close"} />
                      {titleCase(String(approval.decision || approval.status))}
                    </span>
                    <div>
                      <strong>Approval #{approval.id} · Request #{approval.access_request_id}</strong>
                      <span>{approval.decision_reason || "No reviewer note recorded"} · {formatTime(approval.created_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <div className="v2-columns">
            <section className="v2-panel" aria-label="My access requests">
              <header className="v2-panel-head">
                <h2>My access requests</h2>
                <span className="v2-row-note">Created from access-limited answers in Ask</span>
              </header>
              {requests!.length === 0 ? (
                <div className="v2-empty">
                  <MaterialIcon name="lock" />
                  <strong>No access requests yet.</strong>
                  <p>When a question needs more visibility than your access allows, the request flow starts directly in Ask and is tracked here.</p>
                </div>
              ) : (
                requests!.map((request) => (
                  <article key={request.id} className="v2-request-card">
                    <div className="v2-review-head">
                      <span className={`v2-status-chip ${requestStatusChip(request.status)}`}>
                        <MaterialIcon name={requestStatusChip(request.status) === "is-pass" ? "check" : requestStatusChip(request.status) === "is-fail" ? "close" : "schedule"} />
                        {titleCase(request.status)}
                      </span>
                      <span className="v2-review-id">Request #{request.id} · {formatTime(request.created_at)}</span>
                    </div>
                    <p className="v2-request-question">{request.question}</p>
                    <ul className="v2-request-trail">
                      <li>
                        <MaterialIcon name="upload" />
                        Submitted {formatTime(request.created_at)}{request.source_hint ? ` · hint: ${request.source_hint}` : ""}
                      </li>
                      {request.metadata_json?.suggested_approver_email ? (
                        <li>
                          <MaterialIcon name="swap_horiz" />
                          Suggested approver {request.metadata_json.suggested_approver_email}
                        </li>
                      ) : null}
                      {request.metadata_json?.approver_return ? (
                        <li>
                          <MaterialIcon name="warning" />
                          {titleCase(String(request.metadata_json.approver_return.decision || "returned"))}: {String(request.metadata_json.approver_return.decision_reason || "Returned to admin")}
                        </li>
                      ) : null}
                      <li>
                        <MaterialIcon name={request.approved_duration_hours ? "check" : "schedule"} />
                        {request.approved_duration_hours
                          ? `Granted for ${request.approved_duration_hours}h${request.expires_at ? ` · expires ${formatTime(request.expires_at)}` : ""}`
                          : "Awaiting decision"}
                      </li>
                    </ul>
                  </article>
                ))
              )}
            </section>

            <section className="v2-panel" aria-label="Workflow events">
              <header className="v2-panel-head">
                <h2>Workflow events</h2>
                <span className="v2-row-note">Timestamped audit feed</span>
              </header>
              {notifications!.length === 0 ? (
                <div className="v2-empty">
                  <MaterialIcon name="notifications_off" />
                  <strong>No events yet.</strong>
                  <p>Routing, approvals, grants, and expiries land here as they happen.</p>
                </div>
              ) : (
                <ol className="v2-timeline">
                  {notifications!.map((item) => (
                    <li key={item.id} className="v2-timeline-item">
                      <span className={`v2-timeline-dot ${item.status !== "read" ? "is-unread" : ""}`} aria-hidden="true">
                        <MaterialIcon name={eventGlyph(item.event_type)} />
                      </span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.body}</p>
                        <span className="v2-timeline-time">
                          {titleCase(item.event_type)} · {formatTime(item.created_at)}
                          {item.status !== "read" ? (
                            <button type="button" className="v2-timeline-read" onClick={() => markRead(item.id)}>
                              Mark read
                            </button>
                          ) : null}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
