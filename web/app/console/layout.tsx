import { ReactNode } from "react";

import { requireViewer } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  await requireViewer("/console");
  return children;
}
