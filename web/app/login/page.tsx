import { AuthCard } from "@/components/auth-card";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  return (
    <AuthCard
      title="Console Login"
      description="Use your organization’s SSO provider to open the enterprise console."
      nextPath={params.next || "/console"}
      secondaryHref="/get-a-demo"
      secondaryLabel="Request Access"
      showDevLogin={process.env.NEXT_PUBLIC_DEV_MODE === "true"}
    />
  );
}
