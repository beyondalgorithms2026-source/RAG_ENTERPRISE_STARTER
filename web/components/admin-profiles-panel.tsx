"use client";

import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type ProfilesPayload = {
  profiles: GenericMap[];
};

type TuningPayload = {
  live_configuration: GenericMap;
  candidate_drafts: GenericMap[];
  approved_options: Record<string, GenericMap[]>;
  profile_types: string[];
};

type AuditPayload = {
  events: GenericMap[];
};

const TUNING_PROFILE_TYPES = ["llm", "embedding", "reranker", "retrieval"] as const;
const GOVERNED_MODEL_TYPES = ["llm", "embedding", "reranker"] as const;

function formatTimestamp(value: unknown) {
  if (!value) {
    return "Unknown time";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function titleCase(value: unknown) {
  return String(value || "")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusTone(value: unknown) {
  const normalized = String(value || "").toLowerCase();
  if (["live", "active", "approved", "completed"].includes(normalized)) {
    return "is-good";
  }
  if (["draft", "available", "pending"].includes(normalized)) {
    return "";
  }
  return "is-warning";
}

function EmptyState({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="admin-empty-state">
      <span className="material-symbols-outlined">inbox</span>
      <strong>{title}</strong>
      <p>{copy}</p>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="tuning-lab-field">
      <span className="muted-copy">{label}</span>
      {children}
    </label>
  );
}

function modelLabel(profileType: (typeof TUNING_PROFILE_TYPES)[number]) {
  if (profileType === "llm") {
    return "Inference Model";
  }
  if (profileType === "embedding") {
    return "Embedding Model";
  }
  if (profileType === "reranker") {
    return "Reranking Logic";
  }
  return "Retrieval Profile";
}

export function ProfilesAdminPanel() {
  const [profilesPayload, setProfilesPayload] = useState<ProfilesPayload>({ profiles: [] });
  const [tuningPayload, setTuningPayload] = useState<TuningPayload>({
    live_configuration: {},
    candidate_drafts: [],
    approved_options: {},
    profile_types: [],
  });
  const [history, setHistory] = useState<AuditPayload>({ events: [] });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [activating, setActivating] = useState("");
  const [savingDraft, setSavingDraft] = useState(false);
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [visualMode, setVisualMode] = useState(true);
  const [draftName, setDraftName] = useState("Balanced candidate");
  const [draftDescription, setDraftDescription] = useState("Initial M17.b.1 candidate draft based on the current live configuration.");
  const [sampleQuery, setSampleQuery] = useState("How does the Q4 liability clause affect subcontracting?");
  const [selectedProfiles, setSelectedProfiles] = useState<Record<string, string>>({
    llm: "",
    embedding: "",
    reranker: "",
    retrieval: "",
  });
  const [tuningControls, setTuningControls] = useState({
    temperature: 1.1,
    topP: 1.0,
    chunkSize: 512,
    retrievalK: 5,
  });

  async function refresh() {
    setIsLoading(true);
    try {
      const [profiles, tuning, audit] = await Promise.all([
        browserFetch<ProfilesPayload>("/admin/profiles"),
        browserFetch<TuningPayload>("/admin/tuning/configurations"),
        browserFetch<AuditPayload>("/admin/audit-log?action=profile.activate"),
      ]);
      setProfilesPayload(profiles);
      setTuningPayload(tuning);
      setHistory(audit);
      setError("");

      const liveSelected = (tuning.live_configuration?.selected_profiles || {}) as Record<string, string>;
      setSelectedProfiles((current) => {
        const next = { ...current };
        for (const profileType of TUNING_PROFILE_TYPES) {
          next[profileType] = current[profileType] || liveSelected[profileType] || "";
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile and tuning data.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const approvedCounts = useMemo(() => {
    return {
      llm: tuningPayload.approved_options.llm?.length || 0,
      embedding: tuningPayload.approved_options.embedding?.length || 0,
      reranker: tuningPayload.approved_options.reranker?.length || 0,
      retrieval: tuningPayload.approved_options.retrieval?.length || 0,
    };
  }, [tuningPayload]);

  const liveSelected = (tuningPayload.live_configuration?.selected_profiles || {}) as Record<string, string>;
  const liveResolved = (tuningPayload.live_configuration?.resolved_config || {}) as Record<string, GenericMap>;
  const selectedOptionLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const profileType of TUNING_PROFILE_TYPES) {
      const selected = selectedProfiles[profileType] || liveSelected[profileType] || "";
      const options = tuningPayload.approved_options[profileType] || [];
      const match = options.find((option) => String(option.name) === selected);
      labels[profileType] = String(match?.display_name || match?.name || selected || "Not selected");
    }
    return labels;
  }, [liveSelected, selectedProfiles, tuningPayload]);
  const expectedChange = useMemo(() => {
    let deltaCount = 0;
    for (const profileType of TUNING_PROFILE_TYPES) {
      if ((selectedProfiles[profileType] || "") && selectedProfiles[profileType] !== (liveSelected[profileType] || "")) {
        deltaCount += 1;
      }
    }
    if (deltaCount === 0) {
      return "No model swaps yet; this draft mirrors the live baseline.";
    }
    if (deltaCount === 1) {
      return "One governed profile differs from production; useful for the first sandbox benchmark.";
    }
    return `${deltaCount} governed profile selections differ from production; expected change should be validated in M17.b.2 compare runs.`;
  }, [liveSelected, selectedProfiles]);
  const sandboxSummary = editingDraftId
    ? "Editing an existing governed candidate draft. Compare, sandbox execution, and rollout controls intentionally remain disabled until later M17 steps."
    : "This is the M17.b.1 shell: operators can define governed candidate intent now while sandbox execution and live comparison remain gated for later milestones.";

  async function activate(profileType: string, profileName: string) {
    const key = `${profileType}:${profileName}`;
    setActivating(key);
    try {
      await browserFetch("/admin/profiles/active", {
        method: "POST",
        json: { profile_type: profileType, profile_name: profileName },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate profile.");
    } finally {
      setActivating("");
    }
  }

  function loadDraft(draft: GenericMap) {
    setEditingDraftId(Number(draft.id));
    setDraftName(String(draft.name || ""));
    setDraftDescription(String(draft.description || ""));
    setSelectedProfiles({
      llm: String((draft.selected_profiles as GenericMap | undefined)?.llm || liveSelected.llm || ""),
      embedding: String((draft.selected_profiles as GenericMap | undefined)?.embedding || liveSelected.embedding || ""),
      reranker: String((draft.selected_profiles as GenericMap | undefined)?.reranker || liveSelected.reranker || ""),
      retrieval: String((draft.selected_profiles as GenericMap | undefined)?.retrieval || liveSelected.retrieval || ""),
    });
  }

  function resetDraftForm() {
    setEditingDraftId(null);
    setDraftName("Balanced candidate");
    setDraftDescription("Initial M17.b.1 candidate draft based on the current live configuration.");
    setSelectedProfiles({
      llm: liveSelected.llm || "",
      embedding: liveSelected.embedding || "",
      reranker: liveSelected.reranker || "",
      retrieval: liveSelected.retrieval || "",
    });
  }

  async function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingDraft(true);
    try {
      const payload = {
        name: draftName,
        description: draftDescription,
        selected_profiles: selectedProfiles,
      };
      if (editingDraftId) {
        await browserFetch(`/admin/tuning/drafts/${editingDraftId}`, {
          method: "PATCH",
          json: payload,
        });
      } else {
        await browserFetch("/admin/tuning/drafts", {
          method: "POST",
          json: payload,
        });
      }
      resetDraftForm();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save candidate draft.");
    } finally {
      setSavingDraft(false);
    }
  }

  return (
    <div className="admin-route-page">
      <div className="section-head">
        <div>
          <p className="admin-route-eyebrow">Governed Tuning</p>
          <h1>Model Tuning &amp; Experimentation</h1>
          <p>
            Start with the production live configuration, then build a governed candidate in a Stitch-faithful experimentation shell.
            Runtime-safe compare, sandbox execution, and rollout actions land in later M17.b steps.
          </p>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="tuning-lab-shell-frame">
        <div className="tuning-lab-shell-main">
          <section className="tuning-lab-shell-section">
            <div className="tuning-lab-shell-title-row">
              <h2>Current Live Configuration</h2>
              <span className="tuning-lab-live-badge">Production Active</span>
            </div>
            {isLoading ? (
              <EmptyState title="Loading live configuration..." copy="Resolving the current active profile set and live version metadata." />
            ) : tuningPayload.live_configuration?.version_label ? (
              <div className="tuning-lab-live-spotlight">
                <div className="tuning-lab-live-visual" aria-hidden="true">
                  <div className="tuning-lab-live-orb" />
                </div>
                <div className="tuning-lab-live-meta">
                  <div className="tuning-lab-live-detail-grid">
                    {["llm", "embedding", "reranker"].map((profileType) => {
                      const resolved = liveResolved[profileType] || {};
                      const config = (resolved.config || {}) as GenericMap;
                      return (
                        <article key={profileType} className="tuning-lab-live-detail">
                          <span>{profileType === "llm" ? "Inference Model" : profileType === "embedding" ? "Embedding" : "Reranker"}</span>
                          <strong>{String(config.display_name || config.model || liveSelected[profileType] || "Configured")}</strong>
                          <small>{String(config.model || config.dimensions || config.default_mode || liveSelected[profileType] || "resolved")}</small>
                        </article>
                      );
                    })}
                  </div>
                  <div className="tuning-lab-live-footer">
                    <div>
                      <span className="muted-copy">Last Deployment</span>
                      <strong>{formatTimestamp(tuningPayload.live_configuration.updated_at)}</strong>
                    </div>
                    <button type="button" className="button button-secondary" disabled>
                      View Version History
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState title="Live configuration not available." copy="The runtime profile set has not been synced into tuning storage yet." />
            )}
          </section>

          <section className="tuning-lab-shell-section">
            <div className="tuning-lab-shell-title-row tuning-lab-shell-title-row-bottom">
              <div>
                <h2>Experimentation Sandbox</h2>
                <p>Create a new candidate configuration to benchmark against production.</p>
              </div>
              <button type="button" className={`tuning-lab-visual-toggle ${visualMode ? "is-on" : ""}`} onClick={() => setVisualMode((current) => !current)}>
                <span>Visual Mode</span>
                <i />
              </button>
            </div>

            <div className="tuning-lab-shell-note">
              <span className="material-symbols-outlined">experiment</span>
              <p>{sandboxSummary}</p>
            </div>

            <form onSubmit={submitDraft} className="tuning-lab-sandbox-grid">
              <div className="tuning-lab-sandbox-left">
                <section className="tuning-lab-parameter-card">
                  <strong className="tuning-lab-card-eyebrow">Generation Parameters</strong>
                  <div className="tuning-lab-slider-grid">
                    <Field label="Temperature">
                      <div className="tuning-lab-slider-wrap">
                        <div className="tuning-lab-slider-value">{tuningControls.temperature.toFixed(1)}</div>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={tuningControls.temperature}
                          onChange={(event) =>
                            setTuningControls((current) => ({ ...current, temperature: Number(event.target.value) }))
                          }
                        />
                        <p className="muted-copy">Controls randomness. Lowering results in less random completions.</p>
                      </div>
                    </Field>

                    <Field label="Top P">
                      <div className="tuning-lab-slider-wrap">
                        <div className="tuning-lab-slider-value">{tuningControls.topP.toFixed(1)}</div>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={tuningControls.topP}
                          onChange={(event) => setTuningControls((current) => ({ ...current, topP: Number(event.target.value) }))}
                        />
                        <p className="muted-copy">Nucleus sampling tuned visually here; compare execution still lands in M17.b.2.</p>
                      </div>
                    </Field>

                    <Field label="Chunk Size">
                      <div className="tuning-lab-slider-wrap">
                        <div className="tuning-lab-slider-value">{tuningControls.chunkSize}</div>
                        <input
                          type="range"
                          min="128"
                          max="1024"
                          step="64"
                          value={tuningControls.chunkSize}
                          onChange={(event) =>
                            setTuningControls((current) => ({ ...current, chunkSize: Number(event.target.value) }))
                          }
                        />
                        <p className="muted-copy">Character count for each retrieved context block, balanced for speed vs depth.</p>
                      </div>
                    </Field>

                    <Field label="K-Retrieval Count">
                      <div className="tuning-lab-slider-wrap">
                        <div className="tuning-lab-slider-value">{tuningControls.retrievalK}</div>
                        <input
                          type="range"
                          min="1"
                          max="12"
                          step="1"
                          value={tuningControls.retrievalK}
                          onChange={(event) =>
                            setTuningControls((current) => ({ ...current, retrievalK: Number(event.target.value) }))
                          }
                        />
                        <p className="muted-copy">Number of relevant documents to feed into the generator prompt.</p>
                      </div>
                    </Field>
                  </div>
                </section>

                <section className="tuning-lab-selector-card">
                  <div className="tuning-lab-selector-grid">
                    {GOVERNED_MODEL_TYPES.map((profileType) => {
                      const options = tuningPayload.approved_options[profileType] || [];
                      const label =
                        profileType === "llm"
                          ? "Inference Model"
                          : profileType === "embedding"
                            ? "Embedding Model"
                            : "Reranking Logic";
                      return (
                        <Field key={profileType} label={label}>
                          <select
                            value={selectedProfiles[profileType] || ""}
                            onChange={(event) => setSelectedProfiles((current) => ({ ...current, [profileType]: event.target.value }))}
                          >
                            <option value="">Select {label}</option>
                            {options.map((option) => (
                              <option key={String(option.name)} value={String(option.name)}>
                                {String(option.display_name || option.name)}
                              </option>
                            ))}
                          </select>
                        </Field>
                      );
                    })}
                  </div>
                </section>
              </div>

              <aside className="tuning-lab-candidate-rail">
                <div className="tuning-lab-candidate-header">
                  <span className="material-symbols-outlined">science</span>
                  <strong>{draftName || "Candidate Draft"}</strong>
                </div>

                <label className="tuning-lab-candidate-input">
                  <span>Candidate name</span>
                  <input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
                </label>

                <label className="tuning-lab-candidate-input">
                  <span>Candidate rationale</span>
                  <textarea value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} rows={4} />
                </label>

                <article className="tuning-lab-candidate-stat">
                  <span>Model</span>
                  <strong>{selectedOptionLabels.llm}</strong>
                </article>
                <article className="tuning-lab-candidate-stat">
                  <span>Context Strategy</span>
                  <strong>{selectedOptionLabels.retrieval}</strong>
                </article>
                <article className="tuning-lab-candidate-expected">
                  <span>Expected Change</span>
                  <strong>{expectedChange}</strong>
                </article>

                <div className="tuning-lab-candidate-actions">
                  <button type="button" className="button button-primary tuning-lab-run-button" onClick={() => setError("Sandbox execution is gated until M17.b.2. The shell is now visually aligned, but compare runs are not wired yet.")}>
                    Run Sandbox Test
                  </button>
                  {editingDraftId ? (
                    <button type="button" className="button button-secondary" onClick={resetDraftForm}>
                      Cancel Edit
                    </button>
                  ) : null}
                </div>
              </aside>
            </form>
          </section>
        </div>
      </section>

      <section className="card tuning-lab-compare-shell">
        <div className="section-head">
          <div>
            <h2>Test &amp; Compare</h2>
            <p>Shell-only M17.b.1 compare surface. Visual parity is present here; executable compare remains gated until M17.b.2.</p>
          </div>
        </div>
        <div className="tuning-lab-compare-input">
          <input value={sampleQuery} onChange={(event) => setSampleQuery(event.target.value)} placeholder="e.g. How does the Q4 liability clause affect subcontracting?" />
          <button type="button" className="button button-primary" onClick={() => setError("Live-vs-candidate compare is part of M17.b.2. This button is intentionally shell-only right now.")}>
            Run Compare
          </button>
        </div>
        <div className="tuning-lab-compare-grid">
          <article className="tuning-lab-compare-column">
            <div className="tuning-lab-compare-head">
              <h4>Live Production</h4>
              <span>1.2s Latency</span>
            </div>
            <div className="tuning-lab-compare-answer tuning-lab-compare-answer-live">
              “Under the current Q4 guidelines, liability clauses are strictly interpreted to exclude third-party subcontracting unless an explicit waiver is signed by the project lead...”
            </div>
            <div className="tuning-lab-compare-metrics">
              {[
                ["Faithful", "92%"],
                ["Relevance", "88%"],
                ["Halluc.", "0.02"],
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
              <span>0.9s Latency</span>
            </div>
            <div className="tuning-lab-compare-answer tuning-lab-compare-answer-candidate">
              “The Q4 liability structure mandates that any subcontracting activity must be verified against the project lead&apos;s ledger. Per section 12.4, these clauses do not apply to...”
            </div>
            <div className="tuning-lab-compare-metrics tuning-lab-compare-metrics-candidate">
              {[
                ["Faithful", "98%"],
                ["Relevance", "95%"],
                ["Halluc.", "0.01"],
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
        <button type="button" className="button button-secondary" onClick={resetDraftForm}>
          Discard Candidate
        </button>
        <button type="button" className="button button-secondary" onClick={() => setError("Draft persistence is available above. Footer save/promotion actions become the primary rollout bar in later M17.b steps.")}>
          Save as Draft
        </button>
        <button type="button" className="button button-primary" onClick={() => setError("Promotion is intentionally gated until M17.b.3.")}>
          Promote to Live
        </button>
      </footer>

    </div>
  );
}
