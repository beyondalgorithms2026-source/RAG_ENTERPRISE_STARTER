import { SiteMetaPage } from "@/components/site-meta-page";

export default function TermsPage() {
  return (
    <SiteMetaPage
      eyebrow="Policy"
      title="Terms"
      description="This codebase is a milestone-driven enterprise RAG product implementation. The public pages describe the product direction, while production access and commercial terms are handled outside this local repo."
      sections={[
        {
          heading: "Evaluation repo",
          body: "This repository is intended for implementation, testing, and milestone validation. Public CTAs are aligned to that reality rather than promising a self-serve commercial signup path.",
        },
        {
          heading: "Access model",
          body: "Console access is role-aware and depends on the configured authentication mode. Local development flows intentionally differ from production enterprise onboarding.",
        },
        {
          heading: "No hidden trial contract",
          body: "If a route does not provide a working trial, purchase, or registration workflow, it is labeled accordingly and redirected toward the truthful next step instead.",
        },
      ]}
    />
  );
}
