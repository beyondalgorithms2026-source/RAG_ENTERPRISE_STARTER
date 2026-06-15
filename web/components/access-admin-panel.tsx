"use client";

import { useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { TextInput } from "@/components/ui/TextInput";

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

type AccessUser = {
  external_user_id: string;
  email?: string | null;
  display_name?: string | null;
  groups?: string[];
  user_metadata_json?: Record<string, unknown>;
};

type AccessSource = {
  source_id: number;
  file_name: string;
  corpus_name?: string | null;
  sensitivity_label?: string | null;
  seed_source_key?: string | null;
  groups?: string[];
};

type AccessContact = {
  source_id: number;
  contact_role: string;
  contact_external_user_id?: string | null;
  contact_email?: string | null;
  contact_display_name?: string | null;
};

type AccessPayload = {
  summary: Record<string, number>;
  users: AccessUser[];
  groups: Record<string, unknown>[];
  source_acl: AccessSource[];
  source_contacts: AccessContact[];
  org_edges: Record<string, unknown>[];
  direct_grants: Record<string, unknown>[];
  seed_pack_status?: Record<string, unknown>;
};

type AccessExplanation = Record<string, unknown> | null;

function titleCase(value: string) {
  return value.split(/[_\s]+/).filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

export function AccessRequestsAdminPanel() {
  const [accessPayload, setAccessPayload] = useState<AccessPayload | null>(null);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [feedback, setFeedback] = useState("");
  const [routingDrafts, setRoutingDrafts] = useState<Record<number, { sourceIds: string; businessApproverEmail: string; businessApproverDisplayName: string; aclManagerEmail: string; requesterManagerEmail: string; reviewReason: string }>>({});
  const [denyReasons, setDenyReasons] = useState<Record<number, string>>({});
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [membershipDraft, setMembershipDraft] = useState("");
  const [sourceAclDraft, setSourceAclDraft] = useState("");
  const [contactDraft, setContactDraft] = useState("");
  const [userExplain, setUserExplain] = useState<AccessExplanation>(null);
  const [sourceExplain, setSourceExplain] = useState<AccessExplanation>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    const [accessData, requestData] = await Promise.all([
      browserFetch<AccessPayload>("/admin/access"),
      browserFetch<{ access_requests: AccessRequest[] }>("/admin/access-requests"),
    ]);
    setAccessPayload(accessData);
    setRequests(requestData.access_requests);
    if (!selectedUserId && accessData.users.length) {
      setSelectedUserId(accessData.users[0].external_user_id);
      setMembershipDraft((accessData.users[0].groups || []).join(", "));
    }
    if (!selectedSourceId && accessData.source_acl.length) {
      setSelectedSourceId(String(accessData.source_acl[0].source_id));
      setSourceAclDraft((accessData.source_acl[0].groups || []).join(", "));
    }
    setIsLoading(false);
  }

  useEffect(() => {
    refresh().catch((err) => {
      setFeedback(err instanceof Error ? err.message : "Failed to load access workflow state.");
      setIsLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!accessPayload || !selectedUserId) {
      return;
    }
    const user = accessPayload.users.find((item) => item.external_user_id === selectedUserId);
    setMembershipDraft((user?.groups || []).join(", "));
  }, [accessPayload, selectedUserId]);

  useEffect(() => {
    if (!accessPayload || !selectedSourceId) {
      return;
    }
    const source = accessPayload.source_acl.find((item) => String(item.source_id) === selectedSourceId);
    setSourceAclDraft((source?.groups || []).join(", "));
    const contacts = (accessPayload.source_contacts || []).filter((item) => String(item.source_id) === selectedSourceId);
    setContactDraft(
      contacts.map((item) => [item.contact_role, item.contact_email || "", item.contact_display_name || "", item.contact_external_user_id || ""].join("|")).join("\n"),
    );
  }, [accessPayload, selectedSourceId]);

  async function loadUserExplain(externalUserId: string) {
    try {
      const payload = await browserFetch<Record<string, unknown>>(`/admin/access/explain/user/${encodeURIComponent(externalUserId)}`);
      setUserExplain(payload);
      setFeedback("");
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not load user access explanation.");
    }
  }

  async function loadSourceExplain(sourceId: string) {
    try {
      const payload = await browserFetch<Record<string, unknown>>(`/admin/access/explain/source/${sourceId}`);
      setSourceExplain(payload);
      setFeedback("");
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not load source access explanation.");
    }
  }

  useEffect(() => {
    if (selectedUserId) {
      loadUserExplain(selectedUserId).catch(() => undefined);
    }
  }, [selectedUserId]);

  useEffect(() => {
    if (selectedSourceId) {
      loadSourceExplain(selectedSourceId).catch(() => undefined);
    }
  }, [selectedSourceId]);

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

  async function importSeedPack() {
    try {
      await browserFetch("/admin/access/seed-import", { method: "POST", json: {} });
      setFeedback("Enterprise ACL seed pack imported.");
      await refresh();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not import the enterprise ACL seed pack.");
    }
  }

  async function saveMemberships() {
    if (!selectedUserId) {
      return;
    }
    try {
      await browserFetch(`/admin/access/users/${encodeURIComponent(selectedUserId)}/memberships`, {
        method: "PATCH",
        json: { group_names: uniqueSorted(membershipDraft.split(",").map((item) => item.trim())) },
      });
      setFeedback(`Updated memberships for ${selectedUserId}.`);
      await refresh();
      await loadUserExplain(selectedUserId);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not update memberships.");
    }
  }

  async function saveSourceAcl() {
    if (!selectedSourceId) {
      return;
    }
    try {
      await browserFetch(`/admin/access/sources/${selectedSourceId}/acl`, {
        method: "PATCH",
        json: { group_names: uniqueSorted(sourceAclDraft.split(",").map((item) => item.trim())) },
      });
      setFeedback(`Updated ACL groups for source ${selectedSourceId}.`);
      await refresh();
      await loadSourceExplain(selectedSourceId);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not update source ACL.");
    }
  }

  async function saveSourceContacts() {
    if (!selectedSourceId) {
      return;
    }
    const contacts = contactDraft
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [contact_role, contact_email, contact_display_name, contact_external_user_id] = line.split("|").map((item) => item.trim());
        return { contact_role, contact_email, contact_display_name, contact_external_user_id };
      })
      .filter((item) => item.contact_role && item.contact_email);
    try {
      await browserFetch(`/admin/access/sources/${selectedSourceId}/contacts`, {
        method: "PATCH",
        json: { contacts },
      });
      setFeedback(`Updated source contacts for source ${selectedSourceId}.`);
      await refresh();
      await loadSourceExplain(selectedSourceId);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Could not update source contacts.");
    }
  }

  const summary = accessPayload?.summary || {};
  const users = accessPayload?.users || [];
  const sources = accessPayload?.source_acl || [];
  const sourceContacts = accessPayload?.source_contacts || [];
  const selectedSourceContacts = useMemo(
    () => sourceContacts.filter((item) => String(item.source_id) === selectedSourceId),
    [sourceContacts, selectedSourceId],
  );

  return (
    <div className="admin-route-page">
      <section className="admin-section-intro">
        <span>Governed Access</span>
        <h1>Access Requests And Seeded ACL Management</h1>
        <p>Review protected-source posture, route business approvals, execute time-bound direct grants, and maintain the seeded enterprise access model without weakening retrieval-time ACL enforcement.</p>
      </section>

      {feedback ? <div className="error-banner">{feedback}</div> : null}

      <section className="admin-summary-cards">
        <article className="card"><h2>Protected Sources</h2><p>{summary.protected_source_count || 0}</p></article>
        <article className="card"><h2>Active Grants</h2><p>{summary.active_grant_count || 0}</p></article>
        <article className="card"><h2>Seeded Users</h2><p>{Number(accessPayload?.seed_pack_status?.user_count || 0)}</p></article>
        <article className="card"><h2>Groups</h2><p>{summary.group_count || 0}</p></article>
      </section>

      <section className="card">
        <div className="section-head">
          <div>
            <h2>Enterprise Seed Pack</h2>
            <p>Import the reusable seeded users, groups, memberships, sources, and contacts used for ACL and workflow testing.</p>
          </div>
          <button type="button" className="stitch-button stitch-button-primary" onClick={() => importSeedPack()}>Import Seed Pack</button>
        </div>
        <div className="table-list">
          <article className="table-row">
            <div>
              <strong>{Boolean(accessPayload?.seed_pack_status?.ready) ? "Seed pack ready" : "Seed pack not imported yet"}</strong>
              <span className="muted-copy">{Number(accessPayload?.seed_pack_status?.source_count || 0)} seeded sources · {Number(accessPayload?.seed_pack_status?.user_count || 0)} seeded users</span>
            </div>
          </article>
        </div>
      </section>

      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>User Directory</h2>
              <p>Edit memberships for the seeded requesters, approvers, managers, observers, and executives.</p>
            </div>
          </div>
          <label>
            <span>User</span>
            <Select value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)}>
              {users.map((user) => (
                <option key={user.external_user_id} value={user.external_user_id}>{user.display_name || user.email || user.external_user_id}</option>
              ))}
            </Select>
          </label>
          <label>
            <span>Groups (comma separated)</span>
            <TextInput value={membershipDraft} onChange={(event) => setMembershipDraft(event.target.value)} placeholder="public_users, contract_reviewers" />
          </label>
          <div className="toolbar-inline">
            <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={() => saveMemberships()}>Save Memberships</button>
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => selectedUserId && loadUserExplain(selectedUserId)}>Refresh Access Explanation</button>
          </div>
          <div className="table-list">
            {users.map((user) => (
              <article key={user.external_user_id} className="table-row">
                <div>
                  <strong>{user.display_name || user.email || user.external_user_id}</strong>
                  <span className="muted-copy">{(user.groups || []).join(", ") || "No groups"}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="section-head">
            <div>
              <h2>Source ACL Editor</h2>
              <p>Adjust group-based visibility and source contacts without leaving the admin console.</p>
            </div>
          </div>
          <label>
            <span>Source</span>
            <Select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
              {sources.map((source) => (
                <option key={source.source_id} value={String(source.source_id)}>#{source.source_id} · {source.file_name}</option>
              ))}
            </Select>
          </label>
          <label>
            <span>ACL groups (comma separated)</span>
            <TextInput value={sourceAclDraft} onChange={(event) => setSourceAclDraft(event.target.value)} placeholder="legal, executive_access" />
          </label>
          <div className="toolbar-inline">
            <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={() => saveSourceAcl()}>Save ACL</button>
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => selectedSourceId && loadSourceExplain(selectedSourceId)}>Refresh Source Explanation</button>
          </div>
          <label>
            <span>Contacts (`role|email|display|external_user_id`, one per line)</span>
            <Textarea rows={6} value={contactDraft} onChange={(event) => setContactDraft(event.target.value)} placeholder="business_approver|approver@ragenterprise.local|M161 Approver|m161-approver" />
          </label>
          <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => saveSourceContacts()}>Save Contacts</button>
          <div className="table-list">
            {selectedSourceContacts.map((contact, index) => (
              <article key={`${contact.source_id}-${contact.contact_role}-${index}`} className="table-row">
                <div>
                  <strong>{titleCase(contact.contact_role)}</strong>
                  <span className="muted-copy">{contact.contact_display_name || contact.contact_email || contact.contact_external_user_id}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div className="results-grid">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>User Access Explanation</h2>
              <p>Show which sources are reachable through group membership or temporary direct grant.</p>
            </div>
          </div>
          <pre className="rounded-2xl bg-slate-950 p-4 text-xs text-slate-100 overflow-x-auto">{JSON.stringify(userExplain || (isLoading ? { loading: true } : {}), null, 2)}</pre>
        </section>
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Source Access Explanation</h2>
              <p>Show which users can currently see the selected source and why.</p>
            </div>
          </div>
          <pre className="rounded-2xl bg-slate-950 p-4 text-xs text-slate-100 overflow-x-auto">{JSON.stringify(sourceExplain || (isLoading ? { loading: true } : {}), null, 2)}</pre>
        </section>
      </div>

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
                    <label><span>Source ids</span><TextInput value={draft.sourceIds} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, sourceIds: event.target.value } }))} placeholder="Optional if approver will map source ids" /></label>
                    <label><span>Business approver email</span><TextInput value={draft.businessApproverEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, businessApproverEmail: event.target.value } }))} placeholder="owner@example.com" /></label>
                    <label><span>Business approver name</span><TextInput value={draft.businessApproverDisplayName} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, businessApproverDisplayName: event.target.value } }))} placeholder="Source Owner" /></label>
                    <label><span>ACL manager email</span><TextInput value={draft.aclManagerEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, aclManagerEmail: event.target.value } }))} placeholder="acl-manager@example.com" /></label>
                    <label><span>Requester manager email</span><TextInput value={draft.requesterManagerEmail} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, requesterManagerEmail: event.target.value } }))} placeholder="manager@example.com" /></label>
                    <label className="form-span-3"><span>Routing note</span><Textarea rows={2} value={draft.reviewReason} onChange={(event) => setRoutingDrafts((current) => ({ ...current, [request.id]: { ...draft, reviewReason: event.target.value } }))} placeholder="Why this request is being routed or how the source mapping was chosen" /></label>
                    <label className="form-span-3"><span>Close reason</span><Textarea rows={2} value={denyReasons[request.id] || ""} onChange={(event) => setDenyReasons((current) => ({ ...current, [request.id]: event.target.value }))} placeholder="Reason to close without grant" /></label>
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
            <h2>Seeded ACL Coverage</h2>
            <p>Source-level ACL posture, org relationships, and direct grant visibility for the imported enterprise test environment.</p>
          </div>
        </div>
        <div className="table-list">
          {sources.map((item) => (
            <article key={String(item.source_id)} className="table-row">
              <div>
                <strong>#{String(item.source_id)} · {String(item.file_name)}</strong>
                <span className="muted-copy">{String(item.corpus_name || "No corpus")} · {String(item.sensitivity_label || "internal")} · {String(item.seed_source_key || "ad hoc source")}</span>
              </div>
              <div className="table-metrics">
                <span>{Array.isArray(item.groups) && item.groups.length ? item.groups.join(", ") : "No explicit ACL"}</span>
              </div>
            </article>
          ))}
        </div>
        <pre className="rounded-2xl bg-slate-950 p-4 text-xs text-slate-100 overflow-x-auto">{JSON.stringify({ org_edges: accessPayload?.org_edges || [], direct_grants: accessPayload?.direct_grants || [] }, null, 2)}</pre>
      </section>
    </div>
  );
}
