import { PublicFooter, PublicHeader } from "@/components/public-pages";

export function SiteMetaPage({
  title,
  eyebrow,
  description,
  sections,
}: {
  title: string;
  eyebrow: string;
  description: string;
  sections: Array<{ heading: string; body: string }>;
}) {
  return (
    <div className="public-shell">
      <PublicHeader />
      <main className="policy-page">
        <section className="policy-hero">
          <span className="policy-eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </section>
        <section className="policy-card-stack">
          {sections.map((section) => (
            <article key={section.heading} className="policy-card">
              <h2>{section.heading}</h2>
              <p>{section.body}</p>
            </article>
          ))}
        </section>
      </main>
      <PublicFooter compact />
    </div>
  );
}
