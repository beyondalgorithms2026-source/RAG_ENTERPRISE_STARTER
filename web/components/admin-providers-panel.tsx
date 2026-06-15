"use client";

import { useEffect, useState } from "react";

import { browserFetch } from "@/lib/api-browser";

type GenericMap = Record<string, unknown>;

type Profile = {
  name: string;
  is_active: boolean;
  config: GenericMap;
};

type Form = {
  profile_name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
  timeout_s: number;
  structured_output_mode: string;
  reasoning_effort: string;
};

const EMPTY: Form = {
  profile_name: "",
  provider: "openai",
  model: "",
  base_url: "",
  api_key: "",
  timeout_s: 60,
  structured_output_mode: "native_json",
  reasoning_effort: "",
};

export function AdminProvidersPanel() {
  const [providers, setProviders] = useState<string[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedName, setSelectedName] = useState("");
  const [form, setForm] = useState<Form>(EMPTY);
  const [verify, setVerify] = useState<GenericMap | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    try {
      const [providerPayload, profilePayload] = await Promise.all([
        browserFetch<{ providers: string[] }>("/admin/llm/providers"),
        browserFetch<{ profiles: Profile[] }>("/admin/profiles?profile_type=llm"),
      ]);
      setProviders(providerPayload.providers);
      setProfiles(profilePayload.profiles);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load providers.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function update<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function configPayload() {
    const cfg: GenericMap = {
      provider: form.provider,
      model: form.model,
      base_url: form.base_url,
      timeout_s: form.timeout_s,
      structured_output_mode: form.structured_output_mode,
    };
    if (form.api_key) cfg.api_key = form.api_key;
    if (form.reasoning_effort) cfg.reasoning_effort = form.reasoning_effort;
    return cfg;
  }

  function selectProfile(name: string) {
    setSelectedName(name);
    setVerify(null);
    if (!name) {
      setForm(EMPTY);
      return;
    }
    const profile = profiles.find((item) => item.name === name);
    const config = profile?.config || {};
    setForm({
      profile_name: name,
      provider: String(config.provider || "openai"),
      model: String(config.model || ""),
      base_url: String(config.base_url || ""),
      api_key: "",
      timeout_s: Number(config.timeout_s || 60),
      structured_output_mode: String(config.structured_output_mode || "native_json"),
      reasoning_effort: String(config.reasoning_effort || ""),
    });
  }

  async function testConnection() {
    setBusy("verify");
    setError("");
    setVerify(null);
    try {
      setVerify(await browserFetch<GenericMap>("/admin/llm/verify", { method: "POST", json: { config: configPayload() } }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verify failed.");
    } finally {
      setBusy("");
    }
  }

  async function saveAndActivate() {
    if (!form.profile_name) {
      setError("Profile name is required.");
      return;
    }
    setBusy("save");
    setError("");
    setMessage("");
    try {
      const existing = profiles.some((profile) => profile.name === form.profile_name);
      if (existing) {
        await browserFetch(`/admin/profiles/llm/${encodeURIComponent(form.profile_name)}`, {
          method: "PATCH",
          json: { config: configPayload() },
        });
      } else {
        await browserFetch("/admin/profiles", {
          method: "POST",
          json: { profile_type: "llm", profile_name: form.profile_name, config: configPayload() },
        });
      }
      await browserFetch("/admin/profiles/active", { method: "POST", json: { profile_type: "llm", profile_name: form.profile_name } });
      setMessage(`Saved and activated '${form.profile_name}'.`);
      setSelectedName(form.profile_name);
      setForm((current) => ({ ...current, api_key: "" }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save/activate failed.");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div className="section-head">
        <h2>Generation Provider (Bring Your Own Model)</h2>
        <p>Configure and activate the LLM endpoint from the console — OpenAI, Azure OpenAI, vLLM, Ollama, or Anthropic — and test the connection before going live.</p>
      </div>

      {error ? <p style={{ color: "var(--color-text-danger)" }}>{error}</p> : null}
      {message ? <p style={{ color: "var(--color-text-success)" }}>{message}</p> : null}

      <Field label="Existing profile">
        <select value={selectedName} onChange={(event) => selectProfile(event.target.value)}>
          <option value="">Create a new profile</option>
          {profiles.map((profile) => (
            <option key={profile.name} value={profile.name}>
              {profile.name}{profile.is_active ? " (active)" : ""}
            </option>
          ))}
        </select>
      </Field>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
        <Field label="Profile name"><input value={form.profile_name} disabled={Boolean(selectedName)} onChange={(e) => update("profile_name", e.target.value)} placeholder="e.g. azure-gpt4o" /></Field>
        <Field label="Provider">
          <select value={form.provider} onChange={(e) => update("provider", e.target.value)}>
            {providers.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Model"><input value={form.model} onChange={(e) => update("model", e.target.value)} placeholder="gpt-4o-mini" /></Field>
        <Field label="Base URL"><input value={form.base_url} onChange={(e) => update("base_url", e.target.value)} placeholder="https://api.openai.com" /></Field>
        <Field label={`API key (write-only${profiles.find((profile) => profile.name === selectedName)?.config.api_key_configured ? ", configured" : ""})`}><input type="password" value={form.api_key} onChange={(e) => update("api_key", e.target.value)} placeholder={selectedName ? "Leave blank to preserve current key" : "Enter provider key"} autoComplete="new-password" /></Field>
        <Field label="Timeout (s)"><input type="number" min={1} value={form.timeout_s} onChange={(e) => update("timeout_s", Number(e.target.value))} /></Field>
        <Field label="Structured output mode">
          <select value={form.structured_output_mode} onChange={(e) => update("structured_output_mode", e.target.value)}>
            <option value="native_json">native_json</option>
            <option value="prompt_json_only">prompt_json_only</option>
          </select>
        </Field>
        <Field label="Reasoning effort (optional)"><input value={form.reasoning_effort} onChange={(e) => update("reasoning_effort", e.target.value)} placeholder="none / low / …" /></Field>
      </div>

      <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="button button-secondary" onClick={testConnection} disabled={busy === "verify"}>{busy === "verify" ? "Testing…" : "Test connection"}</button>
        <button type="button" className="button button-primary" onClick={saveAndActivate} disabled={busy === "save"}>{busy === "save" ? "Saving…" : "Save & activate"}</button>
        {verify ? (
          <span style={{ fontSize: 13, color: verify.ready ? "var(--color-text-success)" : "var(--color-text-danger)" }}>
            {verify.ready ? "Ready" : "Not ready"} ({String(verify.provider)} · {String(verify.model)}): {String(verify.reason || "")}
          </span>
        ) : null}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
      <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
      {children}
    </label>
  );
}
