import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders grounded answer text as sanitized Markdown (GFM: lists, tables, code,
 * headings, emphasis). react-markdown does NOT render raw HTML by default
 * (rehype-raw is intentionally not used), so embedded markup like <script> is
 * shown as literal text — there is no HTML-injection path. Typography is driven
 * by the `.chat-markdown` rules in globals.css (see web/DESIGN.md).
 */
const COMPONENTS: Components = {
  // Open links in a new tab without leaking the opener.
  a({ node: _node, ...props }) {
    return <a {...props} target="_blank" rel="noreferrer" />;
  },
};

export function AnswerMarkdown({ content }: { content: string }) {
  return (
    <div className="chat-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
