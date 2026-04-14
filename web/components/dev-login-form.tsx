"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { browserFetch } from "@/lib/api-browser";

export function DevLoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("test-user@ragenterprise.local");
  const [password, setPassword] = useState("password123");
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

  return (
    <form className="dev-login-form" onSubmit={onSubmit}>
      <p className="dev-login-copy">
        Development-only shortcut for the two local test accounts. Test User opens the standard workspace. Test Admin opens the admin console. Production SSO remains unchanged.
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
  );
}
