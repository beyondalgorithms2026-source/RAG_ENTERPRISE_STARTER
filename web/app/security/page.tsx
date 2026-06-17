import { SiteMetaPage } from "@/components/site-meta-page";

export default function SecurityPage() {
  return (
    <SiteMetaPage
      eyebrow="Security"
      title="Security"
      description="The product direction for this repository centers on grounded retrieval, citation provenance, and enterprise access controls enforced inside retrieval rather than only in the UI."
      sections={[
        {
          heading: "Retrieval enforcement",
          body: "ACL trimming happens inside retrieval queries so unauthorized chunks cannot leak into the retrieved set or the final citation rail.",
        },
        {
          heading: "Operator visibility",
          body: "Admin routes expose traces, jobs, access posture, and audit events so operators can understand system behavior without querying the database manually.",
        },
        {
          heading: "Local development note",
          body: "Local development environments may enable explicit test-user bypass paths to make first-run validation practical, but those paths are kept visible and milestone-scoped.",
        },
      ]}
    />
  );
}
