"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;
type PolicyVersion = GenericMap & {
  id: number;
  version_number: number;
  status: string;
  match_mode: string;
  similarity_threshold: number;
  ttl_seconds: number;
  max_active_entries: number;
  allow_corpora: string[];
  deny_corpora: string[];
  allow_groups: string[];
  deny_groups: string[];
  allow_questions: string[];
  deny_questions: string[];
};
type Policy = GenericMap & {
  id: number;
  name: string;
  justification: string;
  owner: string;
  review_at?: string | null;
  status: string;
  active_version?: PolicyVersion | null;
  draft_version?: PolicyVersion | null;
  versions?: PolicyVersion[];
};

const emptyForm = {
  name: "",
  justification: "",
  owner: "",
  review_at: "",
  match_mode: "exact",
  similarity_threshold: 0.92,
  ttl_seconds: 900,
  max_active_entries: 1000,
  allow_corpora: [] as string[],
  deny_corpora: [] as string[],
  allow_groups: [] as string[],
  deny_groups: [] as string[],
  allow_questions: "",
  deny_questions: "",
};

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

export function AdminCachePolicyPanel() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [corpora, setCorpora] = useState<string[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [checkQuestion, setCheckQuestion] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [approvalActor, setApprovalActor] = useState("");
  const [result, setResult] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const selected = policies.find((policy) => policy.id === selectedId) || null;
  const positiveScopeCount = form.allow_corpora.length + form.allow_groups.length + lines(form.allow_questions).length;
  const estimatedEligibleQueries = useMemo(() => {
    const allowed = new Set(lines(form.allow_questions).map((item) => item.toLowerCase().replace(/\s+/g, " ")));
    const denied = new Set(lines(form.deny_questions).map((item) => item.toLowerCase().replace(/\s+/g, " ")));
    return recentQueries.filter((item) => {
      const normalized = item.toLowerCase().trim().replace(/\s+/g, " ");
      return allowed.has(normalized) && !denied.has(normalized);
    }).length;
  }, [form.allow_questions, form.deny_questions, recentQueries]);
  const scopeText = useMemo(() => {
    const parts = [
      form.allow_corpora.length ? `corpora ${form.allow_corpora.join(", ")}` : "",
      form.allow_groups.length ? `groups ${form.allow_groups.join(", ")}` : "",
      lines(form.allow_questions).length ? `${lines(form.allow_questions).length} exact questions` : "",
    ].filter(Boolean);
    return parts.length ? `This policy applies only to ${parts.join(" and ")}. All other requests remain uncached.` : "No eligible scope selected. Global caching remains off.";
  }, [form.allow_corpora, form.allow_groups, form.allow_questions]);

  async function refresh(preferredId?: number) {
    const [policyPayload, corpusPayload, accessPayload, queryPayload] = await Promise.all([
      browserFetch<{ policies: Policy[] }>("/admin/semantic-cache/policies"),
      browserFetch<{ corpora: { name: string }[] }>("/admin/corpora"),
      browserFetch<{ groups: { name: string }[] }>("/admin/access"),
      browserFetch<{ query_events?: { question?: string }[] }>("/admin/query-mining"),
    ]);
    setPolicies(policyPayload.policies);
    setCorpora(corpusPayload.corpora.map((item) => item.name));
    setGroups(accessPayload.groups.map((item) => item.name));
    setRecentQueries((queryPayload.query_events || []).map((item) => String(item.question || "")).filter(Boolean));
    if (preferredId) {
      setSelectedId(preferredId);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : "Unable to load cache governance."));
  }, []);

  useEffect(() => {
    if (!selected) {
      setForm(emptyForm);
      return;
    }
    const version = selected.draft_version || selected.active_version;
    setForm({
      name: selected.name || "",
      justification: selected.justification || "",
      owner: selected.owner || "",
      review_at: selected.review_at ? String(selected.review_at).slice(0, 10) : "",
      match_mode: String(version?.match_mode || "exact"),
      similarity_threshold: Number(version?.similarity_threshold ?? 0.92),
      ttl_seconds: Number(version?.ttl_seconds || 900),
      max_active_entries: Number(version?.max_active_entries || 1000),
      allow_corpora: version?.allow_corpora || [],
      deny_corpora: version?.deny_corpora || [],
      allow_groups: version?.allow_groups || [],
      deny_groups: version?.deny_groups || [],
      allow_questions: (version?.allow_questions || []).join("\n"),
      deny_questions: (version?.deny_questions || []).join("\n"),
    });
  }, [selectedId, policies]);

  function toggle(field: "allow_corpora" | "deny_corpora" | "allow_groups" | "deny_groups", value: string) {
    setForm((current) => ({
      ...current,
      [field]: current[field].includes(value) ? current[field].filter((item) => item !== value) : [...current[field], value],
    }));
  }

  function payload() {
    return {
      ...form,
      enabled: false,
      review_at: form.review_at || null,
      allow_questions: lines(form.allow_questions),
      deny_questions: lines(form.deny_questions),
    };
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      const response = selected
        ? await browserFetch<{ policy: Policy }>(`/admin/semantic-cache/policies/${selected.id}`, { method: "PATCH", json: payload() })
        : await browserFetch<{ policy: Policy }>("/admin/semantic-cache/policies", { method: "POST", json: payload() });
      await refresh(response.policy.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Policy draft could not be saved.");
    } finally {
      setBusy("");
    }
  }

  async function action(kind: "check" | "activate" | "disable" | "rollback", versionId?: number) {
    if (!selected) return;
    setBusy(kind);
    setError("");
    try {
      const headers = approvalActor ? { "X-Approval-Actor": approvalActor } : undefined;
      const path = `/admin/semantic-cache/policies/${selected.id}/${kind}`;
      const json = kind === "check" ? { question: checkQuestion, mode: "hybrid" }
        : kind === "activate" ? { confirmation }
          : kind === "rollback" ? { version_id: versionId }
            : undefined;
      const response = await browserFetch<GenericMap>(path, { method: "POST", headers, json });
      setResult(response);
      await refresh(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Policy ${kind} failed.`);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="admin-route-page cache-policy-page">
      <div className="section-head">
        <div>
          <p className="admin-route-eyebrow">Independent Governance</p>
          <h1>Semantic Cache Policy</h1>
          <p>Global default is Off. No answer is reused unless it matches an activated scoped policy.</p>
        </div>
        <Link className="button button-secondary" href="/console/admin/profiles">Back to Profiles</Link>
      </div>
      {error ? <div className="error-banner">{error}</div> : null}

      <section className="card cache-policy-banner">
        <strong>Global default: Off</strong>
        <span>Cache policy changes do not alter model, reranker, retrieval, or sandbox candidates.</span>
      </section>

      <div className="cache-policy-layout">
        <aside className="card cache-policy-list">
          <button className="button button-primary" type="button" onClick={() => setSelectedId(null)}>Create Scoped Policy</button>
          {policies.map((policy) => (
            <button key={policy.id} type="button" className={policy.id === selectedId ? "is-selected" : ""} onClick={() => setSelectedId(policy.id)}>
              <strong>{policy.name}</strong><span>{policy.status}</span>
            </button>
          ))}
        </aside>

        <div className="cache-policy-editor">
          <section className="card">
            <h2>A. Purpose</h2>
            <div className="cache-policy-fields">
              <label><span>Policy name</span><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
              <label><span>Owner</span><input value={form.owner} onChange={(event) => setForm({ ...form, owner: event.target.value })} /></label>
              <label><span>Review date</span><input type="date" value={form.review_at} onChange={(event) => setForm({ ...form, review_at: event.target.value })} /></label>
              <label className="is-wide"><span>Business justification</span><textarea rows={3} value={form.justification} onChange={(event) => setForm({ ...form, justification: event.target.value })} /></label>
            </div>
          </section>

          <section className="card">
            <h2>B. Scope</h2>
            <p className="cache-policy-scope-statement">{scopeText}</p>
            <div className="cache-policy-scope-grid">
              <fieldset><legend>Allowed corpora</legend>{corpora.map((item) => <label key={item}><input type="checkbox" checked={form.allow_corpora.includes(item)} onChange={() => toggle("allow_corpora", item)} />{item}</label>)}</fieldset>
              <fieldset><legend>Denied corpora</legend>{corpora.map((item) => <label key={item}><input type="checkbox" checked={form.deny_corpora.includes(item)} onChange={() => toggle("deny_corpora", item)} />{item}</label>)}</fieldset>
              <fieldset><legend>Allowed ACL groups</legend>{groups.map((item) => <label key={item}><input type="checkbox" checked={form.allow_groups.includes(item)} onChange={() => toggle("allow_groups", item)} />{item}</label>)}</fieldset>
              <fieldset><legend>Denied ACL groups</legend>{groups.map((item) => <label key={item}><input type="checkbox" checked={form.deny_groups.includes(item)} onChange={() => toggle("deny_groups", item)} />{item}</label>)}</fieldset>
            </div>
            <div className="cache-policy-fields">
              <label><span>Approved exact questions, one per line</span><textarea rows={5} value={form.allow_questions} onChange={(event) => setForm({ ...form, allow_questions: event.target.value })} /></label>
              <label><span>Denied exact questions, one per line</span><textarea rows={5} value={form.deny_questions} onChange={(event) => setForm({ ...form, deny_questions: event.target.value })} /></label>
            </div>
          </section>

          <section className="card">
            <h2>C. Safety</h2>
            <details>
              <summary>Advanced settings</summary>
              <div className="cache-policy-fields">
                <label><span>Match mode</span>
                  <select value={form.match_mode} onChange={(event) => setForm({ ...form, match_mode: event.target.value })}>
                    <option value="exact">Exact query</option>
                    <option value="semantic">Semantic similarity</option>
                  </select>
                </label>
                {form.match_mode === "semantic" ? (
                  <label><span>Similarity threshold</span><input type="number" min={0.5} max={0.999} step={0.01} value={form.similarity_threshold} onChange={(event) => setForm({ ...form, similarity_threshold: Number(event.target.value) })} /></label>
                ) : null}
                <label><span>TTL seconds</span><input type="number" min={30} max={86400} value={form.ttl_seconds} onChange={(event) => setForm({ ...form, ttl_seconds: Number(event.target.value) })} /></label>
                <label><span>Maximum active entries</span><input type="number" min={1} max={100000} value={form.max_active_entries} onChange={(event) => setForm({ ...form, max_active_entries: Number(event.target.value) })} /></label>
              </div>
              <p>Locked on: grounded answer, citations, ACL revalidation, and exclusion of no-evidence, approval, tool-action, failed, incomplete, and dry-run responses.</p>
            </details>
          </section>

          <section className="card">
            <h2>D. Impact Review</h2>
            <p>{scopeText}</p>
            <p><strong>{positiveScopeCount}</strong> positive scopes. Deny rules override allows. This changes response reuse, not retrieval quality.</p>
            <p><strong>{estimatedEligibleQueries}</strong> recent exact-query events are currently eligible. Corpus and group scope traffic remains an estimate until a scoped policy check is run.</p>
            <div className="toolbar-inline">
              <button className="button button-primary" type="button" disabled={busy !== "" || positiveScopeCount === 0} onClick={save}>{busy === "save" ? "Saving..." : "Save Policy Draft"}</button>
            </div>
          </section>

          {selected ? (
            <section className="card">
              <h2>Validate And Activate</h2>
              <div className="cache-policy-fields">
                <label><span>Eligible test question</span><input value={checkQuestion} onChange={(event) => setCheckQuestion(event.target.value)} /></label>
                <label><span>Approval actor (required outside local mode)</span><input value={approvalActor} onChange={(event) => setApprovalActor(event.target.value)} /></label>
                <label><span>Type policy name to activate</span><input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>
              </div>
              <div className="toolbar-inline">
                <button className="button button-secondary" type="button" disabled={!checkQuestion || busy !== "" || !selected.draft_version} onClick={() => action("check")}>Run Scoped Policy Check</button>
                <button className="button button-primary" type="button" disabled={confirmation !== selected.name || busy !== "" || !selected.draft_version} onClick={() => action("activate")}>Activate Scoped Policy</button>
                <button className="button button-secondary" type="button" disabled={selected.status !== "active" || busy !== ""} onClick={() => action("disable")}>Disable Policy</button>
              </div>
              {selected.versions?.filter((version) => version.status !== "draft").map((version) => (
                <div key={version.id} className="cache-policy-version">
                  <span>Version {version.version_number} · {version.status}</span>
                  <button className="button button-secondary" type="button" disabled={busy !== "" || version.status === "active"} onClick={() => action("rollback", version.id)}>Rollback to this version</button>
                </div>
              ))}
              {result ? <pre className="cache-policy-result">{JSON.stringify(result, null, 2)}</pre> : null}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
