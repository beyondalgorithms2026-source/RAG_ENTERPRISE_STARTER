import { SiteMetaPage } from "@/components/site-meta-page";

export default function PrivacyPage() {
  return (
    <SiteMetaPage
      eyebrow="Policy"
      title="Privacy"
      description="This repository demonstrates an enterprise retrieval product flow. It is not a production SaaS signup funnel, and it does not include a live customer-data intake pipeline."
      sections={[
        {
          heading: "What this repo stores",
          body: "Local development usage can store uploaded source files, retrieval traces, and admin audit events inside the configured project database and file storage paths.",
        },
        {
          heading: "Authentication and identity",
          body: "Identity handling in this codebase is driven by the configured auth mode. In local dev mode, test-user and test-admin accounts exist only to validate the product workflow safely.",
        },
        {
          heading: "Public-page forms",
          body: "The marketing, demo, and video-tour surfaces in this repository are informational. They do not submit live CRM records or create a production customer account.",
        },
      ]}
    />
  );
}
