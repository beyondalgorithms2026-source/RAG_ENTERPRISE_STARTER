import type { SVGProps } from "react";

type IconName =
  | "spark"
  | "search"
  | "chat"
  | "history"
  | "database"
  | "upload"
  | "hub"
  | "settings"
  | "bell"
  | "send"
  | "copy"
  | "thumb-up"
  | "thumb-down"
  | "shield"
  | "folder"
  | "jobs"
  | "user"
  | "chart"
  | "timeline"
  | "policy"
  | "audit"
  | "plus"
  | "logout"
  | "file"
  | "mail"
  | "drive"
  | "confluence"
  | "check";

export function Icon({ name, className, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  const common = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, className, ...props };
  switch (name) {
    case "spark":
      return <svg {...common}><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8Z" /></svg>;
    case "search":
      return <svg {...common}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>;
    case "chat":
      return <svg {...common}><path d="M5 6h14v9H9l-4 3V6Z" /></svg>;
    case "history":
      return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /></svg>;
    case "database":
      return <svg {...common}><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v10c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 10c0 1.7 3.1 3 7 3s7-1.3 7-3" /></svg>;
    case "upload":
      return <svg {...common}><path d="M12 15V4" /><path d="m8 8 4-4 4 4" /><path d="M4 20h16" /></svg>;
    case "hub":
      return <svg {...common}><circle cx="12" cy="12" r="2.2" /><path d="M12 4v5.8M12 14.2V20M4 12h5.8M14.2 12H20" /></svg>;
    case "settings":
      return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.4.1Z" /></svg>;
    case "bell":
      return <svg {...common}><path d="M15 17H5l1.4-1.4A2 2 0 0 0 7 14.2V11a5 5 0 0 1 10 0v3.2a2 2 0 0 0 .6 1.4L19 17h-4" /><path d="M10 19a2 2 0 0 0 4 0" /></svg>;
    case "send":
      return <svg {...common}><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M22 2 11 13" /></svg>;
    case "copy":
      return <svg {...common}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>;
    case "thumb-up":
      return <svg {...common}><path d="M7 11v10" /><path d="M11 21h6a2 2 0 0 0 2-1.7l1-6A2 2 0 0 0 18 11h-5l.8-4.4A2 2 0 0 0 11.8 4L7 11" /></svg>;
    case "thumb-down":
      return <svg {...common}><path d="M7 13V3" /><path d="M11 3h6a2 2 0 0 1 2 1.7l1 6A2 2 0 0 1 18 13h-5l.8 4.4A2 2 0 0 1 11.8 20L7 13" /></svg>;
    case "shield":
      return <svg {...common}><path d="M12 3 5 6v6c0 4.5 2.6 7.7 7 9 4.4-1.3 7-4.5 7-9V6l-7-3Z" /></svg>;
    case "folder":
      return <svg {...common}><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" /></svg>;
    case "jobs":
      return <svg {...common}><path d="M8 6V4h8v2" /><rect x="4" y="6" width="16" height="14" rx="2" /><path d="M12 10v6M9 13h6" /></svg>;
    case "user":
      return <svg {...common}><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>;
    case "chart":
      return <svg {...common}><path d="M4 20h16" /><path d="M7 16V9M12 16V5M17 16v-3" /></svg>;
    case "timeline":
      return <svg {...common}><path d="M4 6h6M14 6h6M4 18h6M14 18h6" /><circle cx="12" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="M12 8v8" /></svg>;
    case "policy":
      return <svg {...common}><path d="M9 3h6l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" /><path d="M14 3v5h5" /><path d="M8 13h8M8 17h5" /></svg>;
    case "audit":
      return <svg {...common}><path d="M4 6h16M4 12h16M4 18h10" /></svg>;
    case "plus":
      return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
    case "logout":
      return <svg {...common}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></svg>;
    case "file":
      return <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>;
    case "mail":
      return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></svg>;
    case "drive":
      return <svg {...common}><path d="m7 19 5-9 5 9H7ZM7 19 3 12l4-7M17 19l4-7-4-7H7" /></svg>;
    case "confluence":
      return <svg {...common}><path d="m6 7 4 5-4 5" /><path d="m18 7-4 5 4 5" /><path d="M10 12h4" /></svg>;
    case "check":
      return <svg {...common}><path d="m5 12 4 4 10-10" /></svg>;
  }
}
