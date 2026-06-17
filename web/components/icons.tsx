import type { CSSProperties, ReactElement, SVGProps } from "react";

/**
 * Self-hosted inline-SVG icon set. Replaces the former CDN icon font so the UI
 * renders with no external/network dependency (see web/DESIGN.md, UX1).
 *
 * MaterialIcon maps the glyph names already used across the app to bundled line
 * glyphs. Unknown names fall back to a neutral dot so a missing mapping degrades
 * gracefully instead of rendering as literal text. Icons inherit colour via
 * currentColor and size via the CSS `.app-icon` rule (sized in em, so the
 * existing per-context font-size rules keep working).
 */

type Glyph = ReactElement;

const S = {
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

// Base line glyphs. Several glyph names alias onto one base glyph.
const GLYPHS: Record<string, Glyph> = {
  spark: <><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8Z" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  search_plus: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5M11 8v6M8 11h6" /></>,
  explore: <><circle cx="12" cy="12" r="9" /><path d="m15 9-2.5 5.5L7 17l2.5-5.5L15 9Z" /></>,
  chat: <><path d="M5 6h14v9H9l-4 3V6Z" /></>,
  forum: <><path d="M4 5h11v7H8l-4 3V5Z" /><path d="M9 12v3a1 1 0 0 0 1 1h6l3 2v-9a1 1 0 0 0-1-1h-2" /></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /><path d="M12 8v4l3 2" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  sync: <><path d="M4 12a8 8 0 0 1 13-6m1-2v4h-4" /><path d="M20 12a8 8 0 0 1-13 6m-1 2v-4h4" /></>,
  database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v10c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 10c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>,
  upload: <><path d="M12 15V4" /><path d="m8 8 4-4 4 4" /><path d="M4 20h16" /></>,
  inbox: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 13h5l1 2h6l1-2h5" /></>,
  hub: <><circle cx="12" cy="12" r="2.2" /><path d="M12 4v5.8M12 14.2V20M4 12h5.8M14.2 12H20" /><circle cx="12" cy="4" r="1.4" /><circle cx="12" cy="20" r="1.4" /><circle cx="4" cy="12" r="1.4" /><circle cx="20" cy="12" r="1.4" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" /></>,
  tune: <><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></>,
  bell: <><path d="M6 16h12l-1.4-1.4A2 2 0 0 1 16 13.2V10a4 4 0 0 0-8 0v3.2a2 2 0 0 1-.6 1.4L6 16" /><path d="M10 19a2 2 0 0 0 4 0" /></>,
  bell_off: <><path d="M6 16h12l-1.4-1.4A2 2 0 0 1 16 13.2V10a4 4 0 0 0-6.3-3.2M7.6 7.6A4 4 0 0 0 8 10v3.2A2 2 0 0 1 6 16" /><path d="M10 19a2 2 0 0 0 4 0M3 3l18 18" /></>,
  send: <><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M22 2 11 13" /></>,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>,
  thumb_up: <><path d="M7 11v10" /><path d="M11 21h6a2 2 0 0 0 2-1.7l1-6A2 2 0 0 0 18 11h-5l.8-4.4A2 2 0 0 0 11.8 4L7 11" /></>,
  thumb_down: <><path d="M7 13V3" /><path d="M11 3h6a2 2 0 0 1 2 1.7l1 6A2 2 0 0 1 18 13h-5l.8 4.4A2 2 0 0 1 11.8 20L7 13" /></>,
  shield: <><path d="M12 3 5 6v6c0 4.5 2.6 7.7 7 9 4.4-1.3 7-4.5 7-9V6l-7-3Z" /></>,
  shield_check: <><path d="M12 3 5 6v6c0 4.5 2.6 7.7 7 9 4.4-1.3 7-4.5 7-9V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></>,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  badge_check: <><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5L16 9" /></>,
  folder: <><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" /></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
  user: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></>,
  user_circle: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="10" r="2.6" /><path d="M6.5 18a6 6 0 0 1 11 0" /></>,
  chart: <><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="11" width="7" height="10" rx="1.5" /><rect x="3" y="15" width="7" height="6" rx="1.5" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  timeline: <><path d="M4 6h5M15 6h5M4 18h5M15 18h5" /><circle cx="12" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="M12 8v8" /></>,
  document: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" /></>,
  receipt: <><path d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5L10 21l-2.5-1.5L5 21V3Z" /><path d="M9 8h6M9 12h6" /></>,
  card: <><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M3 10h18" /></>,
  swap: <><path d="M7 4 3 8l4 4" /><path d="M3 8h13M17 20l4-4-4-4" /><path d="M21 16H8" /></>,
  code: <><path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 6l-4 12" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="m4 18 5-5 4 4 3-3 4 4" /></>,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>,
  paperclip: <><path d="M20 11.5 12 19a4 4 0 0 1-6-5.3l7-7a2.5 2.5 0 0 1 3.7 3.4l-7 7a1 1 0 0 1-1.5-1.4L11 9" /></>,
  close: <><path d="M6 6 18 18M18 6 6 18" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  link: <><path d="M9 12h6" /><path d="M10 8H8a4 4 0 0 0 0 8h2M14 8h2a4 4 0 0 1 0 8h-2" /></>,
  link_plus: <><path d="M10 8H8a4 4 0 0 0 0 8h2M14 16h2a4 4 0 0 0 3.9-3" /><path d="M9 12h4M18 9v6M15 12h6" /></>,
  external: <><path d="M14 4h6v6" /><path d="M20 4 10 14" /><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" /></>,
  arrow_forward: <><path d="M4 12h15" /><path d="m13 6 6 6-6 6" /></>,
  play: <><path d="M8 5v14l11-7-11-7Z" /></>,
  play_circle: <><circle cx="12" cy="12" r="9" /><path d="M10 9v6l5-3-5-3Z" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  alert: <><path d="M12 4v9M12 17h.01" /><circle cx="12" cy="12" r="9" /></>,
  warning: <><path d="M12 4 2 20h20L12 4Z" /><path d="M12 10v5M12 18h.01" /></>,
  error: <><circle cx="12" cy="12" r="9" /><path d="m9 9 6 6M15 9l-6 6" /></>,
  pending: <><circle cx="12" cy="12" r="9" /><path d="M8 12h.01M12 12h.01M16 12h.01" /></>,
  expand: <><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3" /><path d="M7.5 14h9" /></>,
  check: <><path d="m5 12 4 4 10-10" /></>,
  checklist: <><path d="m3 6 1.5 1.5L7 5M3 13l1.5 1.5L7 12M3 20l1.5 1.5L7 19M11 6h10M11 13h10M11 20h10" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></>,
  mail_unread: <><rect x="3" y="7" width="18" height="12" rx="2" /><path d="m3 9 9 6 9-6" /><circle cx="18" cy="5" r="2.5" /></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></>,
  id: <><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="8.5" cy="11" r="2" /><path d="M6 16a3 3 0 0 1 5 0M14 9h4M14 13h4" /></>,
  group: <><circle cx="9" cy="9" r="3" /><path d="M3 19a6 6 0 0 1 12 0" /><path d="M16 8a3 3 0 0 1 0 6M21 19a6 6 0 0 0-3-5.2" /></>,
  star: <><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3Z" /></>,
  dot: <><circle cx="12" cy="12" r="3.5" /></>,
};

// Glyph-name -> base glyph key (covers the names used across the app).
const ALIASES: Record<string, string> = {
  auto_awesome: "spark", bolt: "spark",
  search: "search", manage_search: "search", search_insights: "search_plus",
  search_spark: "search_plus", travel_explore: "explore", fact_check: "checklist",
  chat: "chat", forum: "forum",
  history: "history", schedule: "clock", work_history: "briefcase",
  sync: "sync", autorenew: "sync", progress_activity: "sync",
  database: "database", dataset: "database", dns: "database",
  upload_file: "upload", move_to_inbox: "inbox", inbox: "inbox",
  hub: "hub", group_work: "group", identity_platform: "id",
  settings: "settings", tune: "tune",
  notifications: "bell", notifications_off: "bell_off",
  send: "send", content_copy: "copy",
  thumb_up: "thumb_up", thumb_down: "thumb_down",
  shield_lock: "shield", security: "shield", health_and_safety: "shield_check",
  verified: "badge_check", verified_user: "shield_check", lock: "lock",
  folder_shared: "folder", folder_zip: "folder",
  person: "user", account_circle: "user_circle",
  analytics: "chart", timeline: "timeline", space_dashboard: "dashboard", view_module: "grid",
  policy: "document", receipt_long: "receipt", assignment: "document",
  article: "document", description: "document", picture_as_pdf: "document",
  draft: "document",
  approval: "check", payments: "card", swap_horiz: "swap", code: "code",
  image: "image", mic: "mic", attach_file: "paperclip",
  close: "close", add: "plus", add_link: "link_plus",
  link: "link", open_in_new: "external", arrow_forward: "arrow_forward",
  play_arrow: "play", play_circle: "play_circle",
  info: "info", priority_high: "alert", warning: "warning", error: "error", pending: "pending",
  fullscreen: "expand", experiment: "flask", science: "flask",
  mark_email_unread: "mail_unread", alternate_email: "mail",
  logout: "logout",
};

/**
 * Brand mark: a document with a magnifying glass (retrieval over documents).
 * Inline SVG (self-hosted, no external/raster asset), themed via currentColor.
 */
export function BrandLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`brand-logo ${className ?? ""}`.trim()}
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h4" />
      <path d="M13 3l5 5v3" />
      <circle cx="15" cy="15" r="4" />
      <path d="m18.1 18.1 3 3" />
    </svg>
  );
}

export function MaterialIcon({
  name,
  className,
  style,
  ...props
}: { name: string; className?: string; style?: CSSProperties } & Omit<SVGProps<SVGSVGElement>, "name" | "style">) {
  const glyph = GLYPHS[ALIASES[name] ?? name] ?? GLYPHS.dot;
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={`app-icon ${className ?? ""}`.trim()}
      style={style}
      {...S}
      {...props}
    >
      {glyph}
    </svg>
  );
}

/**
 * Deterministic initials avatar (no external image host). Seeded by a display
 * name or email so the same identity always renders the same monogram + hue.
 */
export function Monogram({ seed, className, title }: { seed: string; className?: string; title?: string }) {
  const cleaned = (seed || "?").trim();
  const initials =
    cleaned
      .replace(/@.*$/, "")
      .split(/[\s._-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") ||
    cleaned[0]?.toUpperCase() ||
    "?";
  let hash = 0;
  for (let i = 0; i < cleaned.length; i += 1) {
    hash = (hash * 31 + cleaned.charCodeAt(i)) % 360;
  }
  return (
    <span
      className={`monogram ${className ?? ""}`.trim()}
      title={title ?? seed}
      aria-hidden="true"
      style={{ ["--monogram-hue" as string]: `${hash}` }}
    >
      {initials}
    </span>
  );
}
