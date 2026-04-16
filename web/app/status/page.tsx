import { SiteMetaPage } from "@/components/site-meta-page";

export default function StatusPage() {
  return (
    <SiteMetaPage
      eyebrow="Status"
      title="Product Status"
      description="This repository tracks an enterprise RAG build through milestone gates. The visible UI may contain read-only or upcoming surfaces, but primary CTAs should always reflect what is actually live."
      sections={[
        {
          heading: "Current shape",
          body: "The app supports a working public homepage, role-aware console login, user workspace flows, and an increasingly operational admin console.",
        },
        {
          heading: "Private beta reality",
          body: "Self-serve registration, public free-trial activation, and embedded marketing automation are not part of the live product contract in this repository.",
        },
        {
          heading: "Milestone discipline",
          body: "Each milestone moves placeholder surfaces toward truthful, operable behavior and updates the roadmap and status tracker as part of the definition of done.",
        },
      ]}
    />
  );
}
