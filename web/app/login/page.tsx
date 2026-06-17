import { AuthCard } from "@/components/auth-card";
import { serverFetch } from "@/lib/api-server";

type AuthProvidersPayload = {
  auth_enabled: boolean;
  auth_mode: string;
  local_dev_enabled: boolean;
  oidc_configured: boolean;
  sso_available: boolean;
  provider_error: { error: string; message: string } | null;
  providers: Array<{ issuer?: string; authorization_endpoint?: string; token_endpoint?: string }>;
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; dev_login?: string }>;
}) {
  const params = await searchParams;
  let authState: AuthProvidersPayload | null = null;
  try {
    authState = await serverFetch<AuthProvidersPayload>("/auth/providers");
  } catch {
    authState = null;
  }
  const localDevEnabled = authState?.local_dev_enabled ?? process.env.NEXT_PUBLIC_DEV_MODE === "true";
  const ssoAvailable = authState?.sso_available ?? false;
  const devLoginPreferred = Boolean(params.dev_login === "1" || (localDevEnabled && !ssoAvailable));
  const description = devLoginPreferred
    ? "This local environment is configured for developer sign-in. Use a test account below to open the enterprise console."
    : "Use your organization’s SSO provider to open the enterprise console.";
  const infoMessage = devLoginPreferred
    ? "Single sign-on is not configured for this local environment yet. Use the Test User or Test Admin login below for first-run validation."
    : "This product uses enterprise single sign-on only. Local email/password registration is intentionally disabled.";

  return (
    <AuthCard
      title="Console Login"
      description={description}
      nextPath={params.next || "/console"}
      secondaryHref="/get-a-demo"
      secondaryLabel="Request Access"
      showDevLogin={localDevEnabled}
      devLoginPreferred={devLoginPreferred}
      ssoAvailable={ssoAvailable}
      infoMessage={infoMessage}
    />
  );
}
