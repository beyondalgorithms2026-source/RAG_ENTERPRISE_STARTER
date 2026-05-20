"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type AccessRequest = {
  id: number;
  status: string;
  question: string;
  business_reason: string;
  source_hint?: string | null;
  requester_email?: string | null;
  requester_manager_email?: string | null;
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
      selected_source_ids?: number[] | null;
    } | null;
  } | null;
  approved_duration_hours?: number | null;
  expires_at?: string | null;
  targets: { source_id: number }[];
  routing?: {
    business_approver_email?: string | null;
    requester_manager_email?: string | null;
    acl_manager_email?: string | null;
  } | null;
};

type AccessPayload = {
  summary: Record<string, number>;
  users: Record<string, unknown>[];
  groups: Record<string, unknown>[];
  source_acl: Record<string, unknown>[];
};

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function AccessRequestsAdminPanel() {
  const [accessPayload, setAccessPayload] = useState<AccessPayload | null>(null);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [feedback, setFeedback] = useState("");
  const [routingDrafts, setRoutingDrafts] = useState<Record<number, { sourceIds: string; businessApproverEmail: string; businessApproverDisplayName: string; aclManagerEmail: string; requesterManagerEmail: string; reviewReason: string }>>({});
  const [denyReasons, setDenyReasons] = useState<Record<number, string>>({});

  async function refresh() {
    const [accessData, requestData] = await Promise.all([
      browserFetch<AccessPayload>("/admin/access"),
      browserFetch<{ access_requests: AccessRequest[] }>("/admin/access-requests"),
    ]);
    setAccessPayload(accessData);
    setRequests(requestData.access_requests);
  }

  useEffect(() => {
    refresh().catch((err) => setFeedback(err instanceof Error ? err.message : "Failed to load access workflow state."));
  }, []);

  function routingDraftFor(id: number) {
    const request = requests.find((item) => item.id === id);
    const fallbackSourceIds = request?.metadata_json?.approver_return?.selected_source_ids?.length
      ? request.metadata_json.approver_return.selected_source_ids.join(", ")
      : request?.targets?.length
        ? request.targets.map((item) => item.source_id).join(", ")
        : "";
    return routingDrafts[id] || {
      sourceIds: fallbackSourceIds,
      businessApproverEmail: request?.metadata_json?.approver_return?.alternate_business_approver?.contact_email || request?.metadata_json?.suggested_approver_email || "",
      businessApproverDisplayName: request?.metadata_json?.approver_return?.alternate_business_approver?.contact_display_name || request?.metadata_json?.suggested_approver_display_name || "",
      aclManagerEmail: "",
      requesterManagerEmail: request?.requester_manager_email || "",
      reviewReason: "",
    };
  }

  async function routeRequest(request: AccessRequest) {
    const draft = routingDraftFor(request.id);
    try {
      await browserFetch(`/admin/access-requests/${request.id}/route`, {
        method: "POST",
        json: {
          source_ids: draft.sourceIds.split(",").map((value) => Number(value.trim())).filter((value) => Number.isFinite(value) && value > 0),
          business_approver_email: draft.businessApproverEmail || undefined,
          business_approver_display_name: draft.businessApproverDisplayName || undefined,
          acl_manager_email: draft.aclManagerEmail || undefined,
          requester_manager_email: draft.requesterManagerEmail || undefined,
          review_reason: draft.reviewReason || undefined,
        },
      });
      setFeedback(`Access request ${request.id} routed.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not route access request.");
    }
  }

  async function grantRequest(requestId: number) {
    try {
      await browserFetch(`/admin/access-requests/${requestId}/grant`, { method: "POST" });
      setFeedback(`Temporary grant ${requestId} executed.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not grant access.");
    }
  }

  async function denyRequest(requestId: number) {
    try {
      await browserFetch(`/admin/access-requests/${requestId}/deny`, {
        method: "POST",
        json: { reason: denyReasons[requestId] || "Closed without grant." },
      });
      setFeedback(`Access request ${requestId} closed.`);
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not close request.");
    }
  }

  const summary = accessPayload?.summary || {};

  return (
    <div className="admin-route-page">
      <section className="admin-section-intro">
        <span>Governed Access</span>
        <h1>Access Requests</h1>
        <p>Review protected-source posture, route business approvals, and execute time-bound direct grants without weakening retrieval-time ACL enforcement.</p>
      </section>

      {feedback ? <div className="error-banner">{feedback}</div> : null}

      <section className="admin-summary-cards">
        <article className="card"><h2>Protected Sources</h2><p>{summary.protected_source_count || 0}</p></article>
        <article className="card"><h2>Active Grants</h2><p>{summary.active_grant_count || 0}</p></article>
        <article className="card"><h2>Open Sources</h2><p>{summary.open_source_count || 0}</p></article>
        <article className="card"><h2>Groups</h2><p>{summary.group_count || 0}</p></article>
      </section>

      <section className="card">
        <div className="section-head">
          <div>
            <h2>Request Queue</h2>
            <p>Map source hints to source ids, route to the business approver, then execute only the approved temporary grant.</p>
          </div>
        </div>
        <div className="table-list">
          {requests.length === 0 ? (
            <article className="table-row"><div><strong>No access requests yet.</strong><span className="muted-copy">Requests created from access-limited chat states will appear here.</span></div></article>
          ) : (
            requests.map((request) => {
              const draft = routingDraftFor(request.id);
              return (
                <article key={request.id} className="admin-list-item admin-list-item-stacked">
                  <div className="admin-list-main">
                    <div>
                      <strong>#{request.id} {titleCase(request.status)}</strong>
                      <p>{request.question}</p>
                      <small>{request.requester_email || "unknown requester"} · {request.source_hint || "No source hint"} · {request.approved_duration_hours ? `${request.approved_duration_hours}h approved` : "No grant duration yet"}</small>
                      <small>{request.metadata_json?.suggested_approver_email ? `Suggested approver: ${request.metadata_json.suggested_approver_email}` : "No suggested approver"} · {request.requester_manager_email || "No requester manager"}</small>
                      {request.metadata_json?.requester_comment ? <p>{request.metadata_json.requester_comment}</p> : null}
                      {request.metadata_json?.approver_return ? <p>{titleCase(String(request.metadata_json.approver_return.decision || "returned"))}: {String(request.metadata_json.approver_return.decision_reason || "Returned for admin review")}</p> : null}
                    </div>
                    <div className="toolbar-inline">
                      <button type="button" className="stitch-button stitch-button-primary" disabled={request.status !== "business_approved"} onClick={() => grantRequest(request.id)}>Grant</button>
                      <button type="button" className="stitch-button stitch-button-secondary" disabled={request.status === "grant_completed" || request.status === "cancelled"} onClick={() => denyRequest(request.id)}>Close</button>
                    </div>
                  </div>
                  <div className="admin-form-grid">
                    <label><span>Source ids</span><input value={draft.sourceIds} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, sourceIds: event.target.value } }))} placeholder="Optional if approver will map source ids" /></label>
                    <label><span>Business approver email</span><input value={draft.businessApproverEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, businessApproverEmail: event.target.value } }))} placeholder="owner@example.com" /></label>
                    <label><span>Business approver name</span><input value={draft.businessApproverDisplayName} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, businessApproverDisplayName: event.target.value } }))} placeholder="Source Owner" /></label>
                    <label><span>ACL manager email</span><input value={draft.aclManagerEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, aclManagerEmail: event.target.value } }))} placeholder="acl-manager@example.com" /></label>
                    <label><span>Requester manager email</span><input value={draft.requesterManagerEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, requesterManagerEmail: event.target.value } }))} placeholder="manager@example.com" /></label>
                    <label className="form-span-3"><span>Routing note</span><textarea rows={2} value={draft.reviewReason} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, reviewReason: event.target.value } }))} placeholder="Why this request is being routed or how the source mapping was chosen" /></label>
                    <label className="form-span-3"><span>Close reason</span><textarea rows={2} value={denyReasons[request.id] || ""} onChange={(event) => setDenyReasons((current) => ({ ...current, [request.id]: event.target.value }))} placeholder="Reason to close without grant" /></label>
                  </div>
                  <div className="toolbar-inline">
                    <button type="button" className="stitch-button stitch-button-primary stitch-button-small" disabled={request.status === "grant_completed" || request.status === "cancelled"} onClick={() => routeRequest(request)}>Route For Approval</button>
                    <span className="muted-copy">Current route: {request.routing?.business_approver_email || "Not routed"}{request.expires_at ? ` · expires ${request.expires_at}` : ""}</span>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>

      <section className="card">
        <div className="section-head">
          <div>
            <h2>ACL Coverage</h2>
            <p>Use these source ids while mapping request hints to protected documents.</p>
          </div>
        </div>
        <div className="table-list">
          {(accessPayload?.source_acl || []).map((item) => (
            <article key={String(item.source_id)} className="table-row">
              <div>
                <strong>#{String(item.source_id)} · {String(item.file_name)}</strong>
                <span className="muted-copy">{String(item.corpus_name || "No corpus")} · {String(item.sensitivity_label || "internal")}</span>
              </div>
              <div className="table-metrics">
                <span>{Array.isArray(item.groups) && item.groups.length ? (item.groups as string[]).join(", ") : "No explicit ACL"}</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
