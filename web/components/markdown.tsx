import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders grounded answer text as sanitized Markdown (GFM: lists, tables, code,
 * headings, emphasis). react-markdown does NOT render raw HTML by default
 * (rehype-raw is intentionally not used), so embedded markup like <script> is
 * shown as literal text — there is no HTML-injection path. Typography is driven
 * by the `.chat-markdown` rules in globals.css (see web/DESIGN.md).
 *
 * Inline [n] citation markers (where n indexes into `citations`, 1-based) are
 * rewritten to links and rendered as keyboard-focusable superscript chips wired
 * to the evidence rail via onSelectCitation / onHoverCitation.
 */

type CitationLike = { citation_id: string; file_name: string };

const CITE_HREF = "#rag-cite-";

// Turn in-range bare [n] markers into citation links the `a` renderer can catch.
// Skips [n](…) (already a link), [^n] footnotes, and out-of-range numbers.
function injectCitationLinks(content: string, count: number) {
  if (count <= 0) return content;
  return content.replace(/\[(\d{1,3})\](?!\()/g, (match, digits) => {
    const n = Number(digits);
    return n >= 1 && n <= count ? `[${n}](${CITE_HREF}${n})` : match;
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
  const source = list.length ? injectCitationLinks(content, list.length) : content;

  const components: Components = {
    a({ node: _node, href, children, ...props }) {
      if (href && href.startsWith(CITE_HREF)) {
        const n = Number(href.slice(CITE_HREF.length));
        const citation = list[n - 1];
        if (citation) {
          return (
            <sup className="chat-cite-sup">
              <button
                type="button"
                className="chat-cite-chip"
                aria-label={`Citation ${n}: ${citation.file_name}`}
                title={`View source ${n}: ${citation.file_name}`}
                onClick={() => onSelectCitation?.(citation.citation_id)}
                onMouseEnter={() => onHoverCitation?.(citation.citation_id)}
                onMouseLeave={() => onHoverCitation?.(null)}
                onFocus={() => onHoverCitation?.(citation.citation_id)}
                onBlur={() => onHoverCitation?.(null)}
              >
                {n}
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
