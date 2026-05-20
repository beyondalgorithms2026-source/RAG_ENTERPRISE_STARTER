"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { browserFetch } from "@/lib/api-browser";

export function DevLoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("test-user@ragenterprise.local");
  const [password, setPassword] = useState("password123");
  const [customIdentity, setCustomIdentity] = useState({
    name: "M161 Requester",
    email: "requester@ragenterprise.local",
    userId: "m161-requester",
    roles: "user",
    groups: "",
    nextPath: "/console/workspace/chat",
    managerEmail: "manager@ragenterprise.local",
    managerDisplayName: "M161 Manager",
    managerExternalUserId: "m161-manager",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await browserFetch<{ redirect_path: string }>("/auth/local-dev-login", {
        method: "POST",
        json: { email, password, next_path: nextPath },
      });
      router.push(response.redirect_path);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Local dev login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onAssumeIdentity(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await browserFetch<{ redirect_path: string }>("/auth/local-dev-assume", {
        method: "POST",
        json: {
          email: customIdentity.email,
          name: customIdentity.name,
          user_id: customIdentity.userId,
          roles: customIdentity.roles.split(",").map((value) => value.trim()).filter(Boolean),
          groups: customIdentity.groups.split(",").map((value) => value.trim()).filter(Boolean),
          next_path: customIdentity.nextPath || nextPath,
          manager_email: customIdentity.managerEmail || undefined,
          manager_display_name: customIdentity.managerDisplayName || undefined,
          manager_external_user_id: customIdentity.managerExternalUserId || undefined,
        },
      });
      router.push(response.redirect_path);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Custom dev sign-in failed.");
    } finally {
      setLoading(false);
    }
  }

  function applyPreset(preset: {
    name: string;
    email: string;
    userId: string;
    roles: string;
    groups?: string;
    nextPath: string;
    managerEmail?: string;
    managerDisplayName?: string;
    managerExternalUserId?: string;
  }) {
    setCustomIdentity({
      name: preset.name,
      email: preset.email,
      userId: preset.userId,
      roles: preset.roles,
      groups: preset.groups || "",
      nextPath: preset.nextPath,
      managerEmail: preset.managerEmail || "",
      managerDisplayName: preset.managerDisplayName || "",
      managerExternalUserId: preset.managerExternalUserId || "",
    });
  }

  return (
    <div className="dev-login-stack">
      <form className="dev-login-form" onSubmit={onSubmit}>
        <p className="dev-login-copy">
          Development-only shortcut for the two built-in local accounts. Test User opens the standard workspace. Test Admin opens the admin console.
        </p>
        <div className="dev-login-presets">
          <button type="button" className="dev-login-pill" onClick={() => setEmail("test-user@ragenterprise.local")}>
            Test User
          </button>
          <button type="button" className="dev-login-pill" onClick={() => setEmail("test-admin@ragenterprise.local")}>
            Test Admin
          </button>
        </div>
        <label>
          <span>Email</span>
          <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="test-user@ragenterprise.local" />
        </label>
        <label>
          <span>Password</span>
          <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="password123" type="password" />
        </label>
        {error ? <div className="dev-login-error">{error}</div> : null}
        <button className="stitch-button stitch-button-secondary stitch-button-block" type="submit" disabled={loading}>
          {loading ? "Signing In..." : "Sign In With Local Dev Account"}
        </button>
        <div className="dev-login-helper">Use `test-user@ragenterprise.local` or `test-admin@ragenterprise.local` with `password123`.</div>
      </form>

      <form className="dev-login-form" onSubmit={onAssumeIdentity}>
        <p className="dev-login-copy">
          Use this M16.1 testing shortcut to open requester, approver, or manager sessions without hand-editing cookies in the browser.
        </p>
        <div className="dev-login-presets">
          <button
            type="button"
            className="dev-login-pill"
            onClick={() =>
              applyPreset({
                name: "M161 Requester",
                email: "requester@ragenterprise.local",
                userId: "m161-requester",
                roles: "user",
                nextPath: "/console/workspace/chat",
                managerEmail: "manager@ragenterprise.local",
                managerDisplayName: "M161 Manager",
                managerExternalUserId: "m161-manager",
              })
            }
          >
            Requester
          </button>
          <button
            type="button"
            className="dev-login-pill"
            onClick={() =>
              applyPreset({
                name: "M161 Approver",
                email: "approver@ragenterprise.local",
                userId: "m161-approver",
                roles: "approver,user",
                nextPath: "/console/workspace/requests",
              })
            }
          >
            Approver
          </button>
          <button
            type="button"
            className="dev-login-pill"
            onClick={() =>
              applyPreset({
                name: "M161 Manager",
                email: "manager@ragenterprise.local",
                userId: "m161-manager",
                roles: "user",
                nextPath: "/console/workspace/requests",
              })
            }
          >
            Manager
          </button>
        </div>
        <label>
          <span>Name</span>
          <input value={customIdentity.name} onChange={(event) => setCustomIdentity((current) => ({ ...current, name: event.target.value }))} placeholder="M161 Requester" />
        </label>
        <label>
          <span>Email</span>
          <input value={customIdentity.email} onChange={(event) => setCustomIdentity((current) => ({ ...current, email: event.target.value }))} placeholder="requester@ragenterprise.local" />
        </label>
        <label>
          <span>User Id</span>
          <input value={customIdentity.userId} onChange={(event) => setCustomIdentity((current) => ({ ...current, userId: event.target.value }))} placeholder="m161-requester" />
        </label>
        <label>
          <span>Roles</span>
          <input value={customIdentity.roles} onChange={(event) => setCustomIdentity((current) => ({ ...current, roles: event.target.value }))} placeholder="user or approver,user" />
        </label>
        <label>
          <span>Groups</span>
          <input value={customIdentity.groups} onChange={(event) => setCustomIdentity((current) => ({ ...current, groups: event.target.value }))} placeholder="legal-team" />
        </label>
        <label>
          <span>Next Path</span>
          <input value={customIdentity.nextPath} onChange={(event) => setCustomIdentity((current) => ({ ...current, nextPath: event.target.value }))} placeholder="/console/workspace/chat" />
        </label>
        <label>
          <span>Manager Email</span>
          <input value={customIdentity.managerEmail} onChange={(event) => setCustomIdentity((current) => ({ ...current, managerEmail: event.target.value }))} placeholder="manager@ragenterprise.local" />
        </label>
        <label>
          <span>Manager Name</span>
          <input value={customIdentity.managerDisplayName} onChange={(event) => setCustomIdentity((current) => ({ ...current, managerDisplayName: event.target.value }))} placeholder="M161 Manager" />
        </label>
        <label>
          <span>Manager User Id</span>
          <input value={customIdentity.managerExternalUserId} onChange={(event) => setCustomIdentity((current) => ({ ...current, managerExternalUserId: event.target.value }))} placeholder="m161-manager" />
        </label>
        {error ? <div className="dev-login-error">{error}</div> : null}
        <button className="stitch-button stitch-button-secondary stitch-button-block" type="submit" disabled={loading}>
          {loading ? "Signing In..." : "Sign In With Custom Dev Identity"}
        </button>
        <div className="dev-login-helper">For access-workflow tests, use Requester, Approver, and Manager presets here instead of the normal login form.</div>
      </form>
    </div>
  );
}
