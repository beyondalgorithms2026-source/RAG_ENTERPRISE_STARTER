import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders grounded answer text as sanitized Markdown (GFM: lists, tables, code,
 * headings, emphasis). react-markdown does NOT render raw HTML by default
 * (rehype-raw is intentionally not used), so embedded markup like <script> is
 * shown as literal text — there is no HTML-injection path. Typography is driven
 * by the `.chat-markdown` rules in globals.css (see web/DESIGN.md).
 *
 * Inline citation markers in the answer are rendered as keyboard-focusable
 * superscript chips wired to the evidence rail via onSelectCitation /
 * onHoverCitation. The backend emits `[S1]`, `[S2]` … markers (matching each
 * citation's `citation_id`); plain numeric `[1]` markers are also supported as a
 * fallback (mapped 1-based into `citations`). The chip shows the number.
 */

type CitationLike = { citation_id: string; file_name: string };

const CITE_HREF = "#rag-cite-";

// Rewrite inline [S#] (or fallback [n]) markers into citation links the `a`
// renderer can catch. Skips [x](…) (already a link) and [^x] footnotes.
function injectCitationLinks(content: string, citations: CitationLike[]) {
  const byId = new Map(citations.map((citation) => [citation.citation_id.toUpperCase(), citation] as const));
  return content.replace(/\[(S?\d{1,3})\](?!\()/gi, (match, raw: string) => {
    const token = raw.toUpperCase();
    let id: string | undefined;
    let label: string;
    if (token.startsWith("S")) {
      id = byId.has(token) ? token : undefined;
      label = token.slice(1);
    } else {
      const citation = citations[Number(token) - 1];
      id = citation ? citation.citation_id.toUpperCase() : undefined;
      label = token;
    }
    return id && byId.has(id) ? `[${label}](${CITE_HREF}${id})` : match;
  });
}

export function AnswerMarkdown({
  content,
  citations,
  onSelectCitation,
  onHoverCitation,
}: {
  content: string;
  citations?: CitationLike[];
  onSelectCitation?: (citationId: string) => void;
  onHoverCitation?: (citationId: string | null) => void;
}) {
  const list = citations ?? [];
  const byId = new Map(list.map((citation) => [citation.citation_id.toUpperCase(), citation] as const));
  const source = list.length ? injectCitationLinks(content, list) : content;

  const components: Components = {
    a({ node: _node, href, children, ...props }) {
      if (href && href.startsWith(CITE_HREF)) {
        const id = href.slice(CITE_HREF.length).toUpperCase();
        const citation = byId.get(id);
        if (citation) {
          const label = id.replace(/^S/, "");
          return (
            <sup className="chat-cite-sup">
              <button
                type="button"
                className="chat-cite-chip"
                aria-label={`Citation ${label}: ${citation.file_name}`}
                title={`View source ${label}: ${citation.file_name}`}
                onClick={() => onSelectCitation?.(citation.citation_id)}
                onMouseEnter={() => onHoverCitation?.(citation.citation_id)}
                onMouseLeave={() => onHoverCitation?.(null)}
                onFocus={() => onHoverCitation?.(citation.citation_id)}
                onBlur={() => onHoverCitation?.(null)}
              >
                {label}
              </button>
            </sup>
          );
        }
      }
      // Open ordinary links in a new tab without leaking the opener.
      return (
        <a {...props} href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
  };

  return (
    <div className="chat-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
