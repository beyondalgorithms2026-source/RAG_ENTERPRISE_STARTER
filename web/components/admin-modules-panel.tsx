"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import type { AdminModulesPayload } from "@/lib/admin-modules";
import { TextInput } from "@/components/ui/TextInput";
import { Toggle } from "@/components/ui/Toggle";

export function AdminModulesPanel() {
  const [payload, setPayload] = useState<AdminModulesPayload | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [approvalActor, setApprovalActor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    try {
      const data = await browserFetch<AdminModulesPayload>("/admin/modules");
      setPayload(data);
      setSelected(data.enabled_modules);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin modules.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function toggle(module: string) {
    if (module === "overview") return;
    setSelected((current) =>
      current.includes(module) ? current.filter((item) => item !== module) : [...current, module],
    );
  }

  async function persist(enabledModules: string[] | null) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const headers = approvalActor.trim() ? { "X-Approval-Actor": approvalActor.trim() } : undefined;
      const data = await browserFetch<AdminModulesPayload>("/admin/modules", {
        method: "PATCH",
        headers,
        json: { enabled_modules: enabledModules },
      });
      setPayload(data);
      setSelected(data.enabled_modules);
      setMessage(enabledModules === null ? "Runtime override cleared." : "Admin module subset saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update admin modules.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head">
        <h2>Admin Module Manager</h2>
        <p>Choose the deployment-wide console and API subset. This setting is not tenant-scoped.</p>
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}
      {message ? <p style={{ color: "var(--color-text-success)" }}>{message}</p> : null}
      {!payload ? <p style={{ color: "var(--color-text-secondary)" }}>Loading modules...</p> : null}

      {payload ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
            <div className="metric-card"><small>Scenario</small><strong>{payload.scenario_profile}</strong></div>
            <div className="metric-card"><small>Effective source</small><strong>{payload.source}</strong></div>
            <div className="metric-card"><small>Preset modules</small><strong>{payload.preset_modules.length}</strong></div>
            <div className="metric-card"><small>Runtime override</small><strong>{payload.runtime_override ? "Configured" : "None"}</strong></div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
            {payload.modules.map((module) => {
              const checked = selected.includes(module.key);
              const locked = module.key === "overview";
              return (
                <label
                  key={module.key}
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    padding: "1rem",
                    border: "0.5px solid var(--color-border-tertiary)",
                    borderRadius: "var(--border-radius-md)",
                    background: checked ? "var(--color-background-secondary)" : "var(--color-background-primary)",
                  }}
                >
                  <Toggle checked={checked} disabled={locked || busy} onChange={() => toggle(module.key)} />
                  <span style={{ display: "grid", gap: 4 }}>
                    <strong>{module.label}{locked ? " (always on)" : ""}</strong>
                    <small style={{ color: "var(--color-text-secondary)" }}>{module.description}</small>
                    <code>{module.key}</code>
                  </span>
                </label>
              );
            })}
          </div>

          <label style={{ display: "grid", gap: 4, maxWidth: 360 }}>
            <span>Approval actor (required in governed production)</span>
            <TextInput value={approvalActor} onChange={(event) => setApprovalActor(event.target.value)} placeholder="Separate approver user ID" />
          </label>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="stitch-button stitch-button-primary stitch-button-small" disabled={busy} onClick={() => persist(selected)}>
              {busy ? "Saving..." : "Save runtime subset"}
            </button>
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" disabled={busy} onClick={() => persist(null)}>
              Reset to environment or preset
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}
