export const THREAD_STORAGE_KEY = "rag_console_threads_stitch_v1";
export const THREADS_UPDATED_EVENT = "rag:threads-updated";

export type ThreadMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  requestId?: string | null;
  status?: "pending" | "completed" | "failed";
  progressLabel?: string | null;
  progress?: number | null;
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
    freshness?: {
      status: string;
      observed_at?: string | null;
      age_seconds?: number | null;
      threshold_hours: number;
      last_synced_at?: string | null;
      last_ingested_at?: string | null;
      last_enriched_at?: string | null;
    } | null;
  }[];
  usedChunksCount?: number | null;
  mode?: string | null;
  debugInfo?: Record<string, unknown> | null;
  cacheInfo?: {
    status?: string;
    entry_id?: number | null;
    age_seconds?: number | null;
    sources_and_access_checked?: boolean;
    materially_changed?: boolean | null;
    citations_changed?: boolean | null;
    additional_evidence?: boolean | null;
    replaced_entry?: boolean | null;
  } | null;
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

export function upsertThreadRecord(thread: ThreadRecord): ThreadRecord[] {
  const nextThreads = [thread, ...readThreads().filter((item) => item.id !== thread.id)];
  writeThreads(nextThreads);
  return nextThreads;
}

export function updateThreadRecord(threadId: string, updater: (thread: ThreadRecord) => ThreadRecord): ThreadRecord[] {
  const nextThreads = readThreads().map((thread) => (thread.id === threadId ? updater(thread) : thread));
  writeThreads(nextThreads);
  return nextThreads;
}

export function findThreadMessageByRequestId(requestId: string): { threadId: string; messageId: string } | null {
  if (!requestId) {
    return null;
  }
  for (const thread of readThreads()) {
    for (const message of thread.messages) {
      if (message.requestId === requestId) {
        return { threadId: thread.id, messageId: message.id };
      }
    }
  }
  return null;
}
