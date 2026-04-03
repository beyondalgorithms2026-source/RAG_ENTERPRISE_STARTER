export const THREAD_STORAGE_KEY = "rag_console_threads_stitch_v1";
export const THREADS_UPDATED_EVENT = "rag:threads-updated";

export type ThreadMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: {
    citation_id: string;
    source_id: number;
    source_part_id?: number | null;
    chunk_id: number;
    file_name: string;
    source_type: string;
    heading: string;
    locator?: string | null;
    snippet: string;
  }[];
  mode?: string | null;
  debugInfo?: Record<string, unknown> | null;
};

export type ThreadRecord = {
  id: string;
  title: string;
  createdAt: string;
  messages: ThreadMessage[];
};

export function readThreads(): ThreadRecord[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(THREAD_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as ThreadRecord[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function writeThreads(threads: ThreadRecord[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(threads));
  window.dispatchEvent(new Event(THREADS_UPDATED_EVENT));
}
