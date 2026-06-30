"use client";

import { MaterialIcon } from "@/components/icons";
import { AnswerMarkdown } from "@/components/markdown";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";
import { Field } from "@/components/ui/Field";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import type { AskResponse } from "@/lib/types";
import { readThreads, THREADS_UPDATED_EVENT, ThreadMessage, ThreadRecord, updateThreadRecord, upsertThreadRecord, writeThreads } from "@/lib/workspace";

type CitationContextItem = {
  id: number;
  source_id: number;
  source_part_id?: number | null;
  chunk_index: number;
  heading: string;
  chunk_text: string;
  locator_json: Record<string, unknown>;
};

type CitationContextResponse = {
  source_id: number;
  source_file_name: string;
  chunk_id: number;
  target?: CitationContextItem | null;
  neighbors: CitationContextItem[];
  freshness: {
    status: string;
    observed_at?: string | null;
    threshold_hours: number;
  };
};

type EvidenceSection = {
  id: string;
  answer: ThreadMessage;
  question: string;
  label: string;
  citations: NonNullable<ThreadMessage["citations"]>;
};

type FeedbackState = "up" | "down" | null;

type NegativeFeedbackReason =
  | "too_vague"
  | "wrong_document"
  | "wrong_answer"
  | "incomplete_answer"
  | "stale_source_used"
  | "missing_citation"
  | "citation_does_not_support_answer"
  | "should_have_said_not_found"
  | "access_permission_issue";

type NegativeFeedbackDraft = {
  reason: NegativeFeedbackReason | "";
  note: string;
  isOpen: boolean;
  isSubmitting: boolean;
};

type AnswerActionDraft = {
  menuOpen: boolean;
  redoOpen: boolean;
  redoSubmitting: boolean;
  redoMode: "auto" | "hybrid" | "keyword" | "vector";
  redoDepth: "fast" | "strict";
  includeDocuments: boolean;
  includeTables: boolean;
  includeEmails: boolean;
  redoNote: string;
};

type StoredEvidenceRailState = {
  selectedEvidenceMessageId: string | null;
  selectedCitationId: string | null;
  collapsedEvidenceSections: Record<string, boolean>;
};

type AccessRequestDraft = {
  sourceHint: string;
  businessReason: string;
  suggestedApproverEmail: string;
  suggestedApproverDisplayName: string;
  requesterManagerEmail: string;
  requesterManagerDisplayName: string;
  requesterComment: string;
};

type AccessRequestErrors = Partial<Record<keyof AccessRequestDraft, string>>;

type AccessRequestNotice = {
  tone: "error" | "success";
  text: string;
};

type ApprovalResolution = {
  id: number;
  approval_type: string;
  status: string;
  reason: string;
  review_reason?: string | null;
  response_payload_json?: {
    answer?: string | null;
    citations?: ThreadMessage["citations"];
    debug_info?: Record<string, unknown> | null;
  } | null;
};

const EVIDENCE_RAIL_STORAGE_KEY = "rag_console_evidence_rail_v1";
// Consistent "coming soon" label for controls intentionally not wired yet (see web/DESIGN.md).
const COMING_SOON_TITLE = "Coming in a later release.";
const NEGATIVE_FEEDBACK_REASONS: { value: NegativeFeedbackReason; label: string }[] = [
  { value: "too_vague", label: "Too vague" },
  { value: "wrong_document", label: "Wrong document" },
  { value: "wrong_answer", label: "Wrong answer" },
  { value: "incomplete_answer", label: "Incomplete answer" },
  { value: "stale_source_used", label: "Stale / older source used" },
  { value: "missing_citation", label: "Missing citation" },
  { value: "citation_does_not_support_answer", label: "Citation does not support answer" },
  { value: "should_have_said_not_found", label: "Should have said not found" },
  { value: "access_permission_issue", label: "Access / permission issue" },
];

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

function toTitle(input: string) {
  const cleaned = input.trim().replace(/\s+/g, " ");
  return cleaned.length > 40 ? `${cleaned.slice(0, 37)}...` : cleaned;
}

function toEvidenceLabel(question: string, turnNumber: number) {
  const cleaned = question.trim().replace(/\s+/g, " ");
  if (!cleaned) {
    return `Question ${turnNumber}`;
  }
  return cleaned.length > 68 ? `${cleaned.slice(0, 65)}...` : cleaned;
}

function sourceIcon(sourceType: string) {
  const value = sourceType.toLowerCase();
  if (value.includes("pdf")) {
    return { icon: "picture_as_pdf", tone: "is-pdf" };
  }
  if (value.includes("doc") || value.includes("text") || value.includes("md")) {
    return { icon: "description", tone: "is-doc" };
  }
  return { icon: "link", tone: "is-link" };
}

type RailCitation = NonNullable<ThreadMessage["citations"]>[number];

// Group citations by source so the same file is shown once even when several of
// its passages are cited; the group keeps every citation_id for highlight matching.
function groupCitationsBySource(citations: RailCitation[]) {
  const groups: { key: string; rep: RailCitation; items: RailCitation[] }[] = [];
  const seen = new Map<string, { key: string; rep: RailCitation; items: RailCitation[] }>();
  for (const citation of citations) {
    const key = String(citation.source_id ?? citation.file_name ?? citation.citation_id);
    const existing = seen.get(key);
    if (existing) {
      existing.items.push(citation);
    } else {
      const group = { key, rep: citation, items: [citation] };
      seen.set(key, group);
      groups.push(group);
    }
  }
  return groups;
}

function formatSourceTitle(fileName: string) {
  const trimmed = fileName.trim();
  return trimmed.replace(/\.(pdf|docx|doc|txt|md|pptx|xlsx|csv)$/i, "") || trimmed;
}

function isNoContextMessage(message: ThreadMessage | null | undefined) {
  return (message?.content || "").trim() === "Not found in provided sources.";
}

function hasRetrievedEvidenceWithoutCitations(message: ThreadMessage | null | undefined) {
  return Boolean(isNoContextMessage(message) && (message?.usedChunksCount || 0) > 0 && !(message?.citations || []).length);
}

function accessClarification(message: ThreadMessage | null | undefined) {
  const clarification = message?.debugInfo && typeof message.debugInfo.clarification === "object"
    ? (message.debugInfo.clarification as Record<string, unknown>)
    : null;
  return clarification;
}

function approvalDetails(message: ThreadMessage | null | undefined) {
  const approval = message?.debugInfo && typeof message.debugInfo.approval === "object"
    ? (message.debugInfo.approval as Record<string, unknown>)
    : null;
  return approval;
}

function safeJsonParse(value: unknown) {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function buildLocatorSummary(locator: Record<string, unknown>, heading?: string | null, chunkIndex?: number | null) {
  const parts: string[] = [];
  const page = typeof locator.page === "number" ? locator.page : typeof locator.page_number === "number" ? locator.page_number : null;
  const section = typeof locator.section === "string" ? locator.section : typeof locator.heading === "string" ? locator.heading : null;
  const paragraph =
    typeof locator.paragraph === "number"
      ? locator.paragraph
      : typeof locator.paragraph_index === "number"
        ? locator.paragraph_index
        : null;

  if (page !== null) {
    parts.push(`Page ${page}`);
  }
  if (section) {
    parts.push(section);
  } else if (heading) {
    parts.push(heading);
  }
  if (paragraph !== null) {
    parts.push(`Paragraph ${paragraph}`);
  }
  if (!parts.length && typeof chunkIndex === "number") {
    parts.push(`Chunk ${chunkIndex}`);
  }
  return parts.join(" • ");
}

function describeAskProgress(progressLabel?: string | null) {
  const label = (progressLabel || "").toLowerCase();
  if (!label) {
    return "Preparing your grounded answer run.";
  }
  if (label.includes("receiving question")) {
    return "Preparing your request and opening the grounded answer workflow.";
  }
  if (label.includes("searching sources")) {
    return "Retrieval is running against the sources your account can currently access.";
  }
  if (label.includes("retrieved") && label.includes("candidate")) {
    return "Retrieval finished. The system is selecting grounded context before answer generation starts.";
  }
  if (label.includes("generating grounded answer")) {
    return "Grounded answer generation is running against the retrieved evidence.";
  }
  if (label.includes("validating citations")) {
    return "Answer text is ready and citations are being checked before the final response appears.";
  }
  if (label.includes("no grounded context")) {
    return "Retrieval completed, but no usable indexed evidence matched this question.";
  }
  if (label.includes("answer generation failed") || label.includes("answer parsing failed")) {
    return "Retrieval completed, but answer generation could not finish cleanly.";
  }
  if (label.includes("grounded answer ready")) {
    return "Retrieval, grounding, and answer generation have finished.";
  }
  return "Working through retrieval, grounding, and answer generation.";
}

function readStoredEvidenceRailState(threadId: string): StoredEvidenceRailState | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(EVIDENCE_RAIL_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, StoredEvidenceRailState>) : {};
    const state = parsed?.[threadId];
    if (!state || typeof state !== "object") {
      return null;
    }
    return {
      selectedEvidenceMessageId: typeof state.selectedEvidenceMessageId === "string" ? state.selectedEvidenceMessageId : null,
      selectedCitationId: typeof state.selectedCitationId === "string" ? state.selectedCitationId : null,
      collapsedEvidenceSections:
        state.collapsedEvidenceSections && typeof state.collapsedEvidenceSections === "object"
          ? Object.fromEntries(
              Object.entries(state.collapsedEvidenceSections).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean"),
            )
          : {},
    };
  } catch {
    return null;
  }
}

function writeStoredEvidenceRailState(threadId: string, state: StoredEvidenceRailState) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const raw = window.localStorage.getItem(EVIDENCE_RAIL_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, StoredEvidenceRailState>) : {};
    parsed[threadId] = state;
    window.localStorage.setItem(EVIDENCE_RAIL_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // Ignore storage write errors and keep the UI functional.
  }
}

export function ChatWorkspace({ initialThreadId, freshOnLoad = false }: { initialThreadId?: string; freshOnLoad?: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [threads, setThreads] = useState<ThreadRecord[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState(initialThreadId || "");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"auto" | "hybrid" | "keyword" | "vector">("auto");
  const [deepResearch, setDeepResearch] = useState(false);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [selectedEvidenceMessageId, setSelectedEvidenceMessageId] = useState<string | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [hoveredCitationId, setHoveredCitationId] = useState<string | null>(null);
  const [citationContext, setCitationContext] = useState<CitationContextResponse | null>(null);
  const [citationContextError, setCitationContextError] = useState("");
  const [collapsedEvidenceSections, setCollapsedEvidenceSections] = useState<Record<string, boolean>>({});
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, FeedbackState>>({});
  const [negativeFeedbackDraftByMessageId, setNegativeFeedbackDraftByMessageId] = useState<Record<string, NegativeFeedbackDraft>>({});
  const [answerActionDraftByMessageId, setAnswerActionDraftByMessageId] = useState<Record<string, AnswerActionDraft>>({});
  const [actionFlashByMessageId, setActionFlashByMessageId] = useState<Record<string, string>>({});
  const [missingSourceByMessageId, setMissingSourceByMessageId] = useState<Record<string, string>>({});
  const [accessRequestDraftByMessageId, setAccessRequestDraftByMessageId] = useState<Record<string, AccessRequestDraft>>({});
  const [accessModalMessageId, setAccessModalMessageId] = useState<string | null>(null);
  const [accessRequestErrorsByMessageId, setAccessRequestErrorsByMessageId] = useState<Record<string, AccessRequestErrors>>({});
  const [accessRequestNoticeByMessageId, setAccessRequestNoticeByMessageId] = useState<Record<string, AccessRequestNotice>>({});
  const [submittingAccessRequestByMessageId, setSubmittingAccessRequestByMessageId] = useState<Record<string, boolean>>({});
  const evidenceSectionRefs = useRef<Record<string, HTMLElement | null>>({});
  const answerActionMenuTimerRef = useRef<number | null>(null);
  const answerActionMenuHoldRef = useRef<string | null>(null);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".chat-answer-actions")) {
        return;
      }
      clearAnswerActionMenuTimer();
      setAnswerActionDraftByMessageId((current) => {
        let changed = false;
        const next: Record<string, AnswerActionDraft> = {};
        for (const [messageId, draft] of Object.entries(current)) {
          if (draft.menuOpen) {
            changed = true;
            next[messageId] = { ...draft, menuOpen: false };
          } else {
            next[messageId] = draft;
          }
        }
        return changed ? next : current;
      });
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      clearAnswerActionMenuTimer();
      setAnswerActionDraftByMessageId((current) => {
        let changed = false;
        const next: Record<string, AnswerActionDraft> = {};
        for (const [messageId, draft] of Object.entries(current)) {
          if (draft.menuOpen) {
            changed = true;
            next[messageId] = { ...draft, menuOpen: false };
          } else {
            next[messageId] = draft;
          }
        }
        return changed ? next : current;
      });
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      clearAnswerActionMenuTimer();
    };
  }, []);

  useEffect(() => {
    function refresh() {
      const stored = readThreads();
      setThreads(stored);
      setCurrentThreadId((current) => {
        if (initialThreadId) {
          return initialThreadId;
        }
        if (freshOnLoad) {
          return "";
        }
        if (current && stored.some((item) => item.id === current)) {
          return current;
        }
        return "";
      });
    }

    refresh();
    window.addEventListener(THREADS_UPDATED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(THREADS_UPDATED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [freshOnLoad, initialThreadId]);

  const activeThread = useMemo(() => threads.find((item) => item.id === currentThreadId) || null, [threads, currentThreadId]);
  const evidenceSections = useMemo(() => {
    const messages = activeThread?.messages || [];
    const sections: EvidenceSection[] = [];
    let turnNumber = 0;
    for (let index = 0; index < messages.length; index += 1) {
      const message = messages[index];
      if (message.role !== "assistant") {
        continue;
      }
      let questionText = "";
      for (let pointer = index - 1; pointer >= 0; pointer -= 1) {
        if (messages[pointer]?.role === "user") {
          questionText = messages[pointer]?.content || "";
          break;
        }
      }
      turnNumber += 1;
      sections.push({
        id: message.id,
        answer: message,
        question: questionText,
        label: toEvidenceLabel(questionText, turnNumber),
        citations: message.citations || [],
      });
    }
    return sections;
  }, [activeThread]);
  const latestAssistantMessage = evidenceSections.at(-1)?.answer || null;
  const activeEvidenceSection =
    evidenceSections.find((item) => item.id === selectedEvidenceMessageId)
    || evidenceSections.findLast((item) => item.citations.length > 0)
    || evidenceSections.at(-1)
    || null;
  const activeCitations = activeEvidenceSection?.citations || [];
  const selectedCitation = activeCitations.find((item) => item.citation_id === selectedCitationId) || activeCitations[0] || null;
  const hasConversation = Boolean(activeThread?.messages.length);
  const showEvidence = hasConversation && evidenceSections.some((item) => item.citations.length > 0);
  const totalEvidenceCount = evidenceSections.reduce((total, item) => total + item.citations.length, 0);
  const pendingSensitiveApprovalIds = useMemo(() => {
    const ids = new Set<number>();
    for (const thread of threads) {
      for (const message of thread.messages) {
        const approval = approvalDetails(message);
        const approvalId = Number(approval?.approval_id);
        if (approval?.status === "pending" && Number.isFinite(approvalId) && approvalId > 0) {
          ids.add(approvalId);
        }
      }
    }
    return Array.from(ids);
  }, [threads]);
  const latestRetrievalTrace =
    latestAssistantMessage?.debugInfo && typeof latestAssistantMessage.debugInfo.retrieval_trace === "object"
      ? (latestAssistantMessage.debugInfo.retrieval_trace as Record<string, unknown>)
      : {};
  const activeRetrievalPath = String(latestRetrievalTrace.retrieval_path_used || latestRetrievalTrace.resolved_mode || latestAssistantMessage?.mode || "hybrid");
  const activeMethodology = String(latestRetrievalTrace.selected_methodology_label || (mode === "auto" ? "Auto" : mode));
  const activeStrategy = String(latestRetrievalTrace.strategy || latestAssistantMessage?.debugInfo?.strategy || "retrieval_answer");
  const activeDepth = latestRetrievalTrace.deep_research_requested ? "Strict" : "Fast";
  const activeRetrievedCount = activeEvidenceSection?.answer.usedChunksCount || 0;
  const activeCitationCount = activeEvidenceSection?.citations.length || 0;

  useEffect(() => {
    if (!currentThreadId) {
      setSelectedEvidenceMessageId(null);
      setSelectedCitationId(null);
      setCollapsedEvidenceSections({});
      return;
    }
    if (!activeThread) {
      return;
    }

    const defaultSection =
      evidenceSections.findLast((item) => item.citations.length > 0)
      || evidenceSections.at(-1)
      || null;
    const sectionById = new Map(evidenceSections.map((section) => [section.id, section]));
    const storedState = readStoredEvidenceRailState(currentThreadId);
    const nextSelectedEvidenceMessageId =
      (storedState?.selectedEvidenceMessageId && sectionById.has(storedState.selectedEvidenceMessageId))
        ? storedState.selectedEvidenceMessageId
        : (defaultSection?.id || null);
    const nextActiveSection = nextSelectedEvidenceMessageId ? sectionById.get(nextSelectedEvidenceMessageId) || null : null;
    const nextSelectedCitationId =
      (storedState?.selectedCitationId && nextActiveSection?.citations.some((item) => item.citation_id === storedState.selectedCitationId))
        ? storedState.selectedCitationId
        : (nextActiveSection?.citations[0]?.citation_id || null);

    const nextCollapsedEvidenceSections: Record<string, boolean> = {};
    for (const section of evidenceSections) {
      const storedCollapsed = storedState?.collapsedEvidenceSections?.[section.id];
      nextCollapsedEvidenceSections[section.id] =
        typeof storedCollapsed === "boolean" ? storedCollapsed : section.id !== nextSelectedEvidenceMessageId;
    }
    if (nextSelectedEvidenceMessageId) {
      nextCollapsedEvidenceSections[nextSelectedEvidenceMessageId] = false;
    }

    setSelectedEvidenceMessageId(nextSelectedEvidenceMessageId);
    setSelectedCitationId(nextSelectedCitationId);
    setCollapsedEvidenceSections(nextCollapsedEvidenceSections);
  }, [activeThread, currentThreadId, evidenceSections]);

  useEffect(() => {
    if (!currentThreadId || !activeThread) {
      return;
    }
    writeStoredEvidenceRailState(currentThreadId, {
      selectedEvidenceMessageId,
      selectedCitationId,
      collapsedEvidenceSections,
    });
  }, [activeThread, collapsedEvidenceSections, currentThreadId, selectedCitationId, selectedEvidenceMessageId]);

  useEffect(() => {
    if (!selectedCitation) {
      setCitationContext(null);
      setCitationContextError("");
      return;
    }
    let active = true;
    setCitationContext(null);
    setCitationContextError("");
    browserFetch<CitationContextResponse>(`/corpus/${selectedCitation.source_id}/chunks/${selectedCitation.chunk_id}/context?radius=1`)
      .then((payload) => {
        if (active) {
          setCitationContext(payload);
        }
      })
      .catch((err) => {
        if (active) {
          setCitationContextError(err instanceof Error ? err.message : "Failed to load citation context.");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedCitation]);

  useEffect(() => {
    if (!pendingSensitiveApprovalIds.length) {
      return;
    }
    let active = true;
    function syncResolvedSensitiveApprovals(approvals: ApprovalResolution[]) {
      const approvalById = new Map<number, ApprovalResolution>();
      for (const approval of approvals) {
        approvalById.set(approval.id, approval);
      }
      const nextThreads: ThreadRecord[] = readThreads().map((thread) => ({
        ...thread,
        messages: thread.messages.map((message) => {
          const approval = approvalDetails(message);
          const approvalId = Number(approval?.approval_id);
          if (approval?.status !== "pending" || !Number.isFinite(approvalId) || approvalId <= 0) {
            return message;
          }
          const resolved = approvalById.get(approvalId);
          if (!resolved || resolved.status === "pending") {
            return message;
          }
          if (resolved.status === "approved") {
            const resolvedPayload = resolved.response_payload_json || {};
            const resolvedMessage: ThreadMessage = {
              ...message,
              content: typeof resolvedPayload.answer === "string" && resolvedPayload.answer.trim() ? resolvedPayload.answer : message.content,
              citations: Array.isArray(resolvedPayload.citations) ? resolvedPayload.citations : message.citations,
              debugInfo: {
                ...(message.debugInfo || {}),
                ...((resolvedPayload.debug_info && typeof resolvedPayload.debug_info === "object") ? resolvedPayload.debug_info : {}),
                approval: {
                  ...(approval || {}),
                  approval_id: approvalId,
                  status: "approved",
                  review_reason: resolved.review_reason || null,
                },
              },
              status: "completed",
            };
            return resolvedMessage;
          }
          if (resolved.status === "denied") {
            const resolvedMessage: ThreadMessage = {
              ...message,
              content: resolved.review_reason
                ? `This answer was denied during sensitive-information review. Reviewer note: ${resolved.review_reason}`
                : "This answer was denied during sensitive-information review.",
              citations: [],
              debugInfo: {
                ...(message.debugInfo || {}),
                approval: {
                  ...(approval || {}),
                  approval_id: approvalId,
                  status: "denied",
                  review_reason: resolved.review_reason || null,
                },
              },
              status: "completed",
            };
            return resolvedMessage;
          }
          return message;
        }),
      }));
      writeThreads(nextThreads);
      setThreads(nextThreads);
    }
    async function refreshApprovals() {
      try {
        const payload = await browserFetch<{ approvals: ApprovalResolution[] }>("/approvals");
        if (!active) {
          return;
        }
        syncResolvedSensitiveApprovals(payload.approvals || []);
      } catch {
        // Keep polling silent; pending approval text remains visible until the next successful refresh.
      }
    }
    refreshApprovals();
    const intervalId = window.setInterval(refreshApprovals, 5000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [pendingSensitiveApprovalIds.join("|")]);

  function syncThreads(nextThreads: ThreadRecord[]) {
    setThreads(nextThreads);
  }

  function patchThread(threadId: string, updater: (thread: ThreadRecord) => ThreadRecord) {
    const nextThreads = updateThreadRecord(threadId, updater);
    setThreads(nextThreads);
  }

  function askPayload(questionText: string, selectedMode: "auto" | "hybrid" | "keyword" | "vector", strictDepth: boolean, extra: Record<string, unknown> = {}) {
    return {
      question: questionText,
      k_chunks: 6,
      ...(selectedMode === "auto" ? {} : { mode: selectedMode }),
      deep_research: strictDepth,
      ...extra,
    };
  }

  async function submitQuestion() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) {
      return;
    }

    setError("");
    setLastLatencyMs(null);
    setSelectedEvidenceMessageId(null);
    setCitationContext(null);
    setCitationContextError("");
    setIsStreaming(true);

    const threadId = activeThread?.id || createId();
    const placeholderId = createId();
    const existingMessages = activeThread?.messages || [];
    const userMessage: ThreadMessage = {
      id: createId(),
      role: "user",
      content: trimmed,
      status: "completed",
    };
    const assistantPlaceholder: ThreadMessage = {
      id: placeholderId,
      role: "assistant",
      content: "",
      status: "pending",
      progress: 4,
      progressLabel: "Receiving question",
      citations: [],
    };
    const nextThread: ThreadRecord = {
      id: threadId,
      title: activeThread?.title || toTitle(trimmed),
      createdAt: activeThread?.createdAt || new Date().toISOString(),
      messages: [...existingMessages, userMessage, assistantPlaceholder],
    };

    syncThreads(upsertThreadRecord(nextThread));
    setCurrentThreadId(threadId);
    setSelectedEvidenceMessageId(placeholderId);
    setCollapsedEvidenceSections((current) => ({ ...current, [placeholderId]: false }));
    router.push(`/console/workspace/chat/${threadId}`);
    setQuestion("");

    try {
      const response = await fetch(browserApiUrl("/ask/stream"), {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(askPayload(trimmed, mode, deepResearch, { dry_run: false })),
      });
      if (!response.ok || !response.body) {
        throw new Error("Streaming ask failed.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      let finalResult: AskResponse | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        pending += decoder.decode(value, { stream: true });
        const lines = pending.split("\n");
        pending = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }
          const event = JSON.parse(line) as { type: string; progress?: number; label?: string; result?: AskResponse };
          if (event.type === "progress") {
            patchThread(threadId, (thread) => ({
              ...thread,
              messages: thread.messages.map((message) =>
                message.id === placeholderId
                  ? {
                      ...message,
                      status: "pending",
                      progress: event.progress ?? message.progress ?? null,
                      progressLabel: event.label ?? message.progressLabel ?? null,
                    }
                  : message,
              ),
            }));
          }
          if (event.type === "result" && event.result) {
            finalResult = event.result;
          }
        }
      }

      if (!finalResult) {
        throw new Error("No final result returned by /ask/stream.");
      }
      setLastLatencyMs(finalResult.latency_ms);

      const retrievalTrace =
        finalResult.debug_info && typeof finalResult.debug_info.retrieval_trace === "object"
          ? (finalResult.debug_info.retrieval_trace as Record<string, unknown>)
          : null;

      patchThread(threadId, (thread) => ({
        ...thread,
        messages: thread.messages.map((message) =>
          message.id === placeholderId
            ? {
                ...message,
                status: "completed",
                content: finalResult.answer || "No answer returned.",
                requestId: String(retrievalTrace?.request_id || ""),
                citations: finalResult.citations,
                usedChunksCount: finalResult.used_chunks_count,
                mode: finalResult.mode,
                debugInfo: finalResult.debug_info,
                cacheInfo: finalResult.cache_info,
                progress: 100,
                progressLabel: finalResult.answer ? "Grounded answer ready" : "Request completed",
              }
            : message,
        ),
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Workspace request failed.";
      setError(message);
      patchThread(threadId, (thread) => ({
        ...thread,
        messages: thread.messages.map((item) =>
          item.id === placeholderId
            ? {
                ...item,
                status: "failed",
                content: "This request could not be completed right now. Please retry or check whether your source finished indexing.",
                citations: [],
                progress: 100,
                progressLabel: "Request failed",
              }
            : item,
        ),
      }));
    } finally {
      setIsStreaming(false);
    }
  }

  function startFreshThread() {
    setCurrentThreadId("");
    setQuestion("");
    setLastLatencyMs(null);
    setSelectedEvidenceMessageId(null);
    setSelectedCitationId(null);
    setCitationContext(null);
    setCitationContextError("");
    router.push("/console/workspace/chat");
  }

  function flashAction(messageId: string, label: string) {
    setActionFlashByMessageId((current) => ({ ...current, [messageId]: label }));
    window.setTimeout(() => {
      setActionFlashByMessageId((current) => {
        if (!current[messageId]) {
          return current;
        }
        const next = { ...current };
        delete next[messageId];
        return next;
      });
    }, 1200);
  }

  function questionForAssistant(messageId: string) {
    const messages = activeThread?.messages || [];
    const index = messages.findIndex((message) => message.id === messageId);
    for (let pointer = index - 1; pointer >= 0; pointer -= 1) {
      if (messages[pointer]?.role === "user") {
        return messages[pointer].content;
      }
    }
    return "";
  }

  function accessRequestDraftFor(messageId: string): AccessRequestDraft {
    return accessRequestDraftByMessageId[messageId] || {
      sourceHint: missingSourceByMessageId[messageId] || "",
      businessReason: "",
      suggestedApproverEmail: "",
      suggestedApproverDisplayName: "",
      requesterManagerEmail: "",
      requesterManagerDisplayName: "",
      requesterComment: "",
    };
  }

  function negativeFeedbackDraftFor(messageId: string): NegativeFeedbackDraft {
    return negativeFeedbackDraftByMessageId[messageId] || {
      reason: "",
      note: "",
      isOpen: false,
      isSubmitting: false,
    };
  }

  function answerActionDraftFor(messageId: string): AnswerActionDraft {
    return answerActionDraftByMessageId[messageId] || {
      menuOpen: false,
      redoOpen: false,
      redoSubmitting: false,
      redoMode: "auto",
      redoDepth: "fast",
      includeDocuments: true,
      includeTables: true,
      includeEmails: true,
      redoNote: "",
    };
  }

  function patchNegativeFeedbackDraft(messageId: string, patch: Partial<NegativeFeedbackDraft>) {
    setNegativeFeedbackDraftByMessageId((current) => ({
      ...current,
      [messageId]: {
        ...negativeFeedbackDraftFor(messageId),
        ...patch,
      },
    }));
  }

  function patchAnswerActionDraft(messageId: string, patch: Partial<AnswerActionDraft>) {
    setAnswerActionDraftByMessageId((current) => ({
      ...current,
      [messageId]: {
        ...answerActionDraftFor(messageId),
        ...patch,
      },
    }));
  }

  function clearAnswerActionMenuTimer() {
    if (answerActionMenuTimerRef.current !== null) {
      window.clearTimeout(answerActionMenuTimerRef.current);
      answerActionMenuTimerRef.current = null;
    }
  }

  function scheduleAnswerActionMenuClose(messageId: string) {
    clearAnswerActionMenuTimer();
    answerActionMenuTimerRef.current = window.setTimeout(() => {
      if (answerActionMenuHoldRef.current === messageId) {
        scheduleAnswerActionMenuClose(messageId);
        return;
      }
      patchAnswerActionDraft(messageId, { menuOpen: false });
      answerActionMenuTimerRef.current = null;
    }, 4000);
  }

  function openAnswerActionMenu(messageId: string) {
    const willOpen = !answerActionDraftFor(messageId).menuOpen;
    patchAnswerActionDraft(messageId, { menuOpen: willOpen });
    if (willOpen) {
      scheduleAnswerActionMenuClose(messageId);
    } else {
      clearAnswerActionMenuTimer();
    }
  }

  function patchAccessRequestDraft(messageId: string, patch: Partial<AccessRequestDraft>) {
    setAccessRequestDraftByMessageId((current) => ({
      ...current,
      [messageId]: {
        ...accessRequestDraftFor(messageId),
        ...patch,
      },
    }));
    setAccessRequestErrorsByMessageId((current) => {
      const next = { ...(current[messageId] || {}) };
      for (const key of Object.keys(patch) as Array<keyof AccessRequestDraft>) {
        delete next[key];
      }
      return { ...current, [messageId]: next };
    });
    setAccessRequestNoticeByMessageId((current) => {
      if (!current[messageId]) {
        return current;
      }
      const next = { ...current };
      delete next[messageId];
      return next;
    });
  }

  function isPlausibleEmail(value: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
  }

  function validateAccessRequestDraft(messageId: string): AccessRequestErrors {
    const draft = accessRequestDraftFor(messageId);
    const errors: AccessRequestErrors = {};
    if (!draft.businessReason.trim()) {
      errors.businessReason = "Business reason is required.";
    }
    if (draft.suggestedApproverEmail.trim() && !isPlausibleEmail(draft.suggestedApproverEmail)) {
      errors.suggestedApproverEmail = "Enter a valid approver email.";
    }
    if (draft.requesterManagerEmail.trim() && !isPlausibleEmail(draft.requesterManagerEmail)) {
      errors.requesterManagerEmail = "Enter a valid manager email.";
    }
    return errors;
  }

  async function submitFeedback(message: ThreadMessage, feedback: Exclude<FeedbackState, null>) {
    const debugInfo = message.debugInfo || {};
    const retrievalTrace = typeof debugInfo.retrieval_trace === "object" ? debugInfo.retrieval_trace as Record<string, unknown> : {};
    await browserFetch<{ status: string }>("/feedback", {
      method: "POST",
      json: {
        question: questionForAssistant(message.id),
        feedback_type: feedback === "up" ? "helpful" : "not_helpful",
        rating: feedback,
        request_id: message.requestId || String(retrievalTrace.request_id || ""),
        answer_path: String(debugInfo.answer_generation_path || ""),
        metadata_json: { message_id: message.id },
      },
    });
  }

  async function setFeedback(message: ThreadMessage, feedback: Exclude<FeedbackState, null>) {
    if (feedback === "down") {
      setFeedbackByMessageId((current) => ({ ...current, [message.id]: "down" }));
      patchNegativeFeedbackDraft(message.id, { isOpen: true });
      return;
    }
    setFeedbackByMessageId((current) => {
      const nextValue = current[message.id] === feedback ? null : feedback;
      return { ...current, [message.id]: nextValue };
    });
    patchNegativeFeedbackDraft(message.id, { isOpen: false });
    try {
      await submitFeedback(message, feedback);
      flashAction(message.id, "Marked helpful");
    } catch {
      flashAction(message.id, "Feedback saved locally only");
    }
  }

  async function submitNegativeFeedback(message: ThreadMessage) {
    const draft = negativeFeedbackDraftFor(message.id);
    if (!draft.reason) {
      flashAction(message.id, "Choose a reason");
      return;
    }
    const debugInfo = message.debugInfo || {};
    const retrievalTrace = typeof debugInfo.retrieval_trace === "object" ? debugInfo.retrieval_trace as Record<string, unknown> : {};
    const activeProfileSnapshot =
      (retrievalTrace.active_profiles && typeof retrievalTrace.active_profiles === "object")
        ? retrievalTrace.active_profiles as Record<string, unknown>
        : {};
    patchNegativeFeedbackDraft(message.id, { isSubmitting: true });
    try {
      await browserFetch<{ status: string; negative_feedback_id?: number | null }>("/feedback", {
        method: "POST",
        json: {
          question: questionForAssistant(message.id),
          feedback_type: "not_helpful",
          rating: "down",
          negative_reason: draft.reason,
          note: draft.note,
          answer_text: message.content,
          citations_json: message.citations || [],
          used_chunks_count: message.usedChunksCount || (Array.isArray(message.citations) ? message.citations.length : 0),
          active_profile_snapshot_json: activeProfileSnapshot,
          request_id: message.requestId || String(retrievalTrace.request_id || ""),
          answer_path: String(debugInfo.answer_generation_path || ""),
          metadata_json: { message_id: message.id },
        },
      });
      setFeedbackByMessageId((current) => ({ ...current, [message.id]: "down" }));
      patchNegativeFeedbackDraft(message.id, { isOpen: false, isSubmitting: false });
      flashAction(message.id, "Answer issue logged");
    } catch (err) {
      patchNegativeFeedbackDraft(message.id, { isSubmitting: false });
      flashAction(message.id, err instanceof Error ? err.message : "Feedback failed");
    }
  }

  function redoFiltersFor(draft: AnswerActionDraft) {
    const enabled = [draft.includeDocuments, draft.includeTables, draft.includeEmails].filter(Boolean).length;
    if (enabled !== 1) {
      return undefined;
    }
    if (draft.includeTables) return { source_type: "xlsx" };
    if (draft.includeEmails) return { source_type: "eml" };
    return undefined;
  }

  async function retryAnswer(message: ThreadMessage, retryVariant: "try_again" | "add_details") {
    const draft = answerActionDraftFor(message.id);
    const originalQuestion = questionForAssistant(message.id);
    const threadId = activeThread?.id;
    if (!threadId || !originalQuestion || isStreaming) {
      return;
    }
    const placeholderId = createId();
    patchAnswerActionDraft(message.id, { redoSubmitting: true, menuOpen: false });
    setIsStreaming(true);
    setError("");
    patchThread(threadId, (thread) => ({
      ...thread,
      messages: [
        ...thread.messages,
        {
          id: placeholderId,
          role: "assistant",
          content: "",
          status: "pending",
          progress: 8,
          progressLabel: "Retrying with selected search settings",
          citations: [],
        },
      ],
    }));
    try {
      const quickKeywordRetry = retryVariant === "try_again" && (!(message.citations || []).length || isNoContextMessage(message));
      const selectedMode = retryVariant === "try_again" ? (quickKeywordRetry ? "keyword" : "auto") : draft.redoMode;
      const selectedDepth = retryVariant === "try_again" || selectedMode === "keyword" ? "fast" : draft.redoDepth;
      const strictDepth = selectedDepth === "strict";
      const retryNote = retryVariant === "add_details" ? draft.redoNote.trim() : "";
      const retryFilters = retryVariant === "add_details" ? redoFiltersFor(draft) : undefined;
      const response = await browserFetch<AskResponse>("/ask", {
        method: "POST",
        json: askPayload(originalQuestion, selectedMode, strictDepth, {
          ...(retryNote ? { search_instruction: retryNote } : {}),
          ...(retryFilters ? { filters: retryFilters } : {}),
          bypass_cache: true,
        }),
      });
      setLastLatencyMs(response.latency_ms);
      const retrievalTrace =
        response.debug_info && typeof response.debug_info.retrieval_trace === "object"
          ? (response.debug_info.retrieval_trace as Record<string, unknown>)
          : null;
      const redoRequestId = String(retrievalTrace?.request_id || "");
      patchThread(threadId, (thread) => ({
        ...thread,
        messages: thread.messages.map((item) =>
          item.id === placeholderId
            ? {
                ...item,
                status: "completed",
                content: response.answer || "No answer returned.",
                requestId: redoRequestId,
                citations: response.citations,
                usedChunksCount: response.used_chunks_count,
                mode: response.mode,
                debugInfo: response.debug_info,
                cacheInfo: response.cache_info,
                progress: 100,
                progressLabel: "Retry complete",
              }
            : item,
        ),
      }));
      await browserFetch<{ status: string }>("/feedback/retry", {
        method: "POST",
        json: {
          question: originalQuestion,
          original_request_id: message.requestId || "",
          redo_request_id: redoRequestId,
          selected_mode: selectedMode === "auto" ? null : selectedMode,
          retry_variant: retryVariant,
          depth: selectedDepth,
          include_documents: draft.includeDocuments,
          include_tables: draft.includeTables,
          include_emails: draft.includeEmails,
          note: retryNote,
          metadata_json: { original_message_id: message.id, redo_message_id: placeholderId },
        },
      });
      patchAnswerActionDraft(message.id, { redoOpen: false, redoSubmitting: false });
      flashAction(message.id, retryVariant === "try_again" ? "Retry started with fast search" : "Retried with selected settings");
    } catch (err) {
      patchAnswerActionDraft(message.id, { redoSubmitting: false });
      setError(err instanceof Error ? err.message : "Retry failed.");
      patchThread(threadId, (thread) => ({
        ...thread,
        messages: thread.messages.map((item) =>
          item.id === placeholderId
            ? { ...item, status: "failed", content: "Retry failed.", citations: [], progress: 100, progressLabel: "Retry failed" }
            : item,
        ),
      }));
    } finally {
      setIsStreaming(false);
    }
  }

  async function submitMissingSource(message: ThreadMessage) {
    const suggestedSource = accessRequestDraftFor(message.id).sourceHint.trim();
    if (!suggestedSource) {
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "error", text: "Add a file, link, connector, or source hint first." },
      }));
      return;
    }
    const debugInfo = message.debugInfo || {};
    const retrievalTrace = typeof debugInfo.retrieval_trace === "object" ? debugInfo.retrieval_trace as Record<string, unknown> : {};
    try {
      await browserFetch<{ status: string }>("/feedback", {
        method: "POST",
        json: {
          question: questionForAssistant(message.id),
          feedback_type: "missing_evidence",
          reason: "user_suggested_source",
          suggested_source: suggestedSource,
          request_id: message.requestId || String(retrievalTrace.request_id || ""),
          answer_path: "not_found",
          metadata_json: { message_id: message.id },
        },
      });
      setMissingSourceByMessageId((current) => ({ ...current, [message.id]: "" }));
      patchAccessRequestDraft(message.id, { sourceHint: "" });
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "success", text: "Source hint sent to admins." },
      }));
    } catch (err) {
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "error", text: err instanceof Error ? err.message : "Could not send suggestion." },
      }));
    }
  }

  async function submitAccessRequest(message: ThreadMessage) {
    const draft = accessRequestDraftFor(message.id);
    const debugInfo = message.debugInfo || {};
    const retrievalTrace = typeof debugInfo.retrieval_trace === "object" ? (debugInfo.retrieval_trace as Record<string, unknown>) : {};
    const errors = validateAccessRequestDraft(message.id);
    if (Object.keys(errors).length) {
      setAccessRequestErrorsByMessageId((current) => ({ ...current, [message.id]: errors }));
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "error", text: "Fix the highlighted fields before requesting access." },
      }));
      return;
    }
    setSubmittingAccessRequestByMessageId((current) => ({ ...current, [message.id]: true }));
    try {
      const result = await browserFetch<{ status: string; access_request: { id: number } }>("/access-requests", {
        method: "POST",
        json: {
          question: questionForAssistant(message.id),
          business_reason: draft.businessReason.trim(),
          source_hint: draft.sourceHint.trim() || null,
          suggested_approver_email: draft.suggestedApproverEmail.trim() || null,
          suggested_approver_display_name: draft.suggestedApproverDisplayName.trim() || null,
          requester_manager_email: draft.requesterManagerEmail.trim() || null,
          requester_manager_display_name: draft.requesterManagerDisplayName.trim() || null,
          requester_comment: draft.requesterComment.trim() || null,
          request_id: message.requestId || String(retrievalTrace.request_id || ""),
          answer_path: "not_found",
          metadata_json: { message_id: message.id },
        },
      });
      setMissingSourceByMessageId((current) => ({ ...current, [message.id]: "" }));
      setAccessRequestDraftByMessageId((current) => ({
        ...current,
        [message.id]: {
          sourceHint: "",
          businessReason: "",
          suggestedApproverEmail: "",
          suggestedApproverDisplayName: "",
          requesterManagerEmail: "",
          requesterManagerDisplayName: "",
          requesterComment: "",
        },
      }));
      setAccessRequestErrorsByMessageId((current) => ({ ...current, [message.id]: {} }));
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "success", text: `Access request #${result.access_request.id} sent for admin review.` },
      }));
    } catch (err) {
      setAccessRequestNoticeByMessageId((current) => ({
        ...current,
        [message.id]: { tone: "error", text: err instanceof Error ? err.message : "Could not send access request." },
      }));
    } finally {
      setSubmittingAccessRequestByMessageId((current) => ({ ...current, [message.id]: false }));
    }
  }

  async function copyAnswer(message: ThreadMessage) {
    if (typeof navigator === "undefined" || !message.content) {
      return;
    }
    try {
      await navigator.clipboard.writeText(message.content);
      flashAction(message.id, "Copied");
    } catch {
      setError("Copy failed for this browser session.");
    }
  }

  async function refreshCachedAnswer(message: ThreadMessage) {
    const entryId = message.cacheInfo?.entry_id;
    const originalQuestion = questionForAssistant(message.id);
    if (!entryId || !originalQuestion || isStreaming) {
      return;
    }
    setError("");
    setIsStreaming(true);
    patchThread(activeThread!.id, (thread) => ({
      ...thread,
      messages: thread.messages.map((item) =>
        item.id === message.id
          ? { ...item, status: "pending", progress: 8, progressLabel: "Refreshing with latest documents" }
          : item,
      ),
    }));
    try {
      const response = await browserFetch<AskResponse>("/ask", {
        method: "POST",
        json: askPayload(originalQuestion, (message.mode as "auto" | "hybrid" | "keyword" | "vector" | null) || mode, deepResearch, {
          bypass_cache: true,
          refresh_cache_entry_id: entryId,
        }),
      });
      setLastLatencyMs(response.latency_ms);
      const retrievalTrace =
        response.debug_info && typeof response.debug_info.retrieval_trace === "object"
          ? (response.debug_info.retrieval_trace as Record<string, unknown>)
          : null;
      patchThread(activeThread!.id, (thread) => ({
        ...thread,
        messages: thread.messages.map((item) =>
          item.id === message.id
            ? {
                ...item,
                status: "completed",
                content: response.answer || "No answer returned.",
                requestId: String(retrievalTrace?.request_id || item.requestId || ""),
                citations: response.citations,
                usedChunksCount: response.used_chunks_count,
                mode: response.mode,
                debugInfo: response.debug_info,
                cacheInfo: response.cache_info,
                progress: 100,
                progressLabel: "Refreshed with latest documents",
              }
            : item,
        ),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Answer refresh failed.");
      patchThread(activeThread!.id, (thread) => ({
        ...thread,
        messages: thread.messages.map((item) =>
          item.id === message.id ? { ...item, status: "completed", progress: 100, progressLabel: "Refresh failed" } : item,
        ),
      }));
    } finally {
      setIsStreaming(false);
    }
  }

  const contextLocator = buildLocatorSummary(
    safeJsonParse(citationContext?.target?.locator_json),
    citationContext?.target?.heading || selectedCitation?.heading || null,
    citationContext?.target?.chunk_index ?? null,
  );
  const contextTitle = citationContext?.source_file_name || selectedCitation?.file_name || "Retrieved source";
  const contextTitleLabel = formatSourceTitle(contextTitle);

  // Bridge from Search: arrive at /chat?q=… → prefill the composer (not auto-sent;
  // asking runs the LLM, so the user confirms by pressing Ask).
  useEffect(() => {
    const incoming = searchParams.get("q");
    if (incoming) {
      setQuestion(incoming);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!accessModalMessageId) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setAccessModalMessageId(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [accessModalMessageId]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      setAnswerActionDraftByMessageId((current) => {
        const next: Record<string, AnswerActionDraft> = {};
        let changed = false;
        for (const [messageId, draft] of Object.entries(current)) {
          next[messageId] = draft.menuOpen ? { ...draft, menuOpen: false } : draft;
          changed = changed || draft.menuOpen;
        }
        return changed ? next : current;
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Select a citation from a pill, an inline answer chip, or an evidence card:
  // mark it active (loads chunk context via effect), expand its section, scroll it in.
  function selectCitation(evidenceId: string, citationId: string) {
    setSelectedEvidenceMessageId(evidenceId);
    setSelectedCitationId(citationId);
    setCollapsedEvidenceSections((current) => ({ ...current, [evidenceId]: false }));
    window.setTimeout(() => {
      evidenceSectionRefs.current[evidenceId]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }, 0);
  }

  return (
    <div className="chat-page">
      {hasConversation ? (
        <div className="chat-metadata-bar">
          <div className="chat-mode-pill">
            <MaterialIcon name="bolt" className="icon-fill" />
            Mode: {activeMethodology}
          </div>
          <div>Depth: <strong>{activeDepth}</strong></div>
          <div>Strategy: <strong>{activeStrategy.replace(/_/g, " ")}</strong></div>
          <div>Latency: <strong>{lastLatencyMs ? `${lastLatencyMs}ms` : "—"}</strong></div>
          <div>Retrieved: <strong>{activeRetrievedCount}</strong></div>
          <div>Citations: <strong>{activeCitationCount}</strong></div>
          <div title="How this answer was retrieved.">Route: <strong>{(activeRetrievalPath || "—").replace(/_/g, " ")}</strong></div>
          <div className="chat-speed-toggle">
            <button
              type="button"
              className={!deepResearch ? "is-active" : ""}
              onClick={() => setDeepResearch(false)}
              title="Fast uses the standard retrieval path for lower latency."
            >
              Fast
            </button>
            <button
              type="button"
              className={deepResearch ? "is-active" : ""}
              onClick={() => setDeepResearch(true)}
              title="Strict enables deeper retrieval for higher recall."
            >
              Strict
            </button>
            <span className="chat-speed-caption">{deepResearch ? "Deeper retrieval" : "Lower latency"}</span>
          </div>
          {activeEvidenceSection?.question ? (
            <Link
              href={`/console/workspace/search?q=${encodeURIComponent(activeEvidenceSection.question)}`}
              className="chat-search-bridge"
              title="See the raw retrieved sources for this question in Search"
            >
              <MaterialIcon name="manage_search" />
              Search sources
            </Link>
          ) : null}
        </div>
      ) : null}

      <div className="chat-layout">
        <main className="chat-main">
          <div className="chat-scroll">
            <div className="chat-utility-row">
              <button type="button" className="chat-new-thread" onClick={startFreshThread} aria-label="New thread" title="Start a new thread">
                <MaterialIcon name="auto_awesome" className="icon-fill" />
              </button>
              {error ? <div className="chat-error-banner" role="alert">{error}</div> : null}
            </div>

            {activeThread?.messages.length ? (
              activeThread.messages.map((message) =>
                message.role === "user" ? (
                  <div key={message.id} className="chat-user-row">
                    <div className="chat-user-bubble">{message.content}</div>
                  </div>
                ) : (
                  <div key={message.id} id={`message-${message.id}`} className="chat-answer-row">
                    <div className="chat-answer-avatar">
                      <MaterialIcon name="auto_awesome" className="icon-fill" />
                    </div>
                    <div className="chat-answer-column">
                      <article
                        className={`chat-answer-card ${message.status === "pending" ? "is-pending" : ""} ${message.status === "failed" ? "is-failed" : ""}`}
                        aria-live="polite"
                      >
                        {message.status === "pending" ? (
                          <div className="chat-progress-card" role="status">
                            <div className="chat-progress-head">
                              <strong>{message.progressLabel || "Working on your answer"}</strong>
                              <span aria-hidden="true">{message.progress || 0}%</span>
                            </div>
                            <div className="chat-progress-bar">
                              <div style={{ width: `${message.progress || 0}%` }} />
                            </div>
                            <p className="chat-progress-copy">{describeAskProgress(message.progressLabel)}</p>
                          </div>
                        ) : (
                          <>
                            {message.cacheInfo?.status === "hit" ? (
                              <div className="chat-cache-notice">
                                <div>
                                  <strong>Reused answer</strong>
                                  <span>
                                    {typeof message.cacheInfo.age_seconds === "number"
                                      ? `${Math.max(1, Math.round(message.cacheInfo.age_seconds / 60))} min old`
                                      : "Recently saved"}
                                    {message.cacheInfo.sources_and_access_checked ? " · Sources and access checked" : ""}
                                  </span>
                                </div>
                                <button type="button" onClick={() => refreshCachedAnswer(message)} disabled={isStreaming}>
                                  Refresh using latest documents
                                </button>
                              </div>
                            ) : null}
                            <AnswerMarkdown
                              content={message.content}
                              citations={message.citations ?? []}
                              onSelectCitation={(citationId) => selectCitation(message.id, citationId)}
                              onHoverCitation={setHoveredCitationId}
                            />
                            {isNoContextMessage(message) ? (
                              <div className="chat-no-context-card">
                                <strong>{hasRetrievedEvidenceWithoutCitations(message) ? "Evidence was retrieved, but no cited answer could be produced." : "No grounded evidence was retrieved for this question."}</strong>
                                <p>
                                  {hasRetrievedEvidenceWithoutCitations(message)
                                    ? "Use the answer actions menu to retry with exact keyword search or add a search instruction."
                                    : String(accessClarification(message)?.access_message || "Try exact wording from the source, confirm the file finished indexing, or tell admins where this information should exist.")}
                                </p>
                                <p>If you know the likely owner, team, project, or manager, add that context before requesting access. Without it, routing can become a needle-in-a-haystack exercise for admins.</p>
                                {accessClarification(message)?.request_access_supported ? (
                                  <>
                                    <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => setAccessModalMessageId(message.id)}>
                                      Request access to a source
                                    </button>
                                    {accessModalMessageId === message.id ? (
                                      <div className="chat-modal-backdrop" role="dialog" aria-modal="true" aria-label="Request source access" onClick={() => setAccessModalMessageId(null)}>
                                        <div className="chat-modal" onClick={(event) => event.stopPropagation()}>
                                          <div className="chat-modal-head">
                                            <strong>Request access to a source</strong>
                                            <button type="button" className="chat-modal-close" aria-label="Close dialog" onClick={() => setAccessModalMessageId(null)}>
                                              <MaterialIcon name="close" />
                                            </button>
                                          </div>
                                  <div className="chat-access-request-form">
                                    <div className="chat-access-request-field">
                                      <label htmlFor={`source-hint-${message.id}`}>File, link, connector, or source hint</label>
                                      <input
                                        id={`source-hint-${message.id}`}
                                        value={accessRequestDraftFor(message.id).sourceHint}
                                        onChange={(event) => patchAccessRequestDraft(message.id, { sourceHint: event.target.value })}
                                        placeholder="Optional. Add any document, contract, customer, or upload clue"
                                      />
                                    </div>
                                    <div className="chat-access-request-field">
                                      <label htmlFor={`business-reason-${message.id}`}>Business reason <span>*</span></label>
                                      <textarea
                                        id={`business-reason-${message.id}`}
                                        rows={2}
                                        className={accessRequestErrorsByMessageId[message.id]?.businessReason ? "is-invalid" : ""}
                                        value={accessRequestDraftFor(message.id).businessReason}
                                        onChange={(event) => patchAccessRequestDraft(message.id, { businessReason: event.target.value })}
                                        placeholder="Explain what you are trying to complete and why access is needed"
                                      />
                                      {accessRequestErrorsByMessageId[message.id]?.businessReason ? <span className="chat-access-request-error">{accessRequestErrorsByMessageId[message.id]?.businessReason}</span> : null}
                                    </div>
                                    <div className="chat-access-request-grid">
                                      <div className="chat-access-request-field">
                                        <label htmlFor={`approver-email-${message.id}`}>Suggested approver email</label>
                                        <input
                                          id={`approver-email-${message.id}`}
                                          className={accessRequestErrorsByMessageId[message.id]?.suggestedApproverEmail ? "is-invalid" : ""}
                                          value={accessRequestDraftFor(message.id).suggestedApproverEmail}
                                          onChange={(event) => patchAccessRequestDraft(message.id, { suggestedApproverEmail: event.target.value })}
                                          placeholder="Optional"
                                        />
                                        {accessRequestErrorsByMessageId[message.id]?.suggestedApproverEmail ? <span className="chat-access-request-error">{accessRequestErrorsByMessageId[message.id]?.suggestedApproverEmail}</span> : null}
                                      </div>
                                      <div className="chat-access-request-field">
                                        <label htmlFor={`approver-name-${message.id}`}>Suggested approver name</label>
                                        <input
                                          id={`approver-name-${message.id}`}
                                          value={accessRequestDraftFor(message.id).suggestedApproverDisplayName}
                                          onChange={(event) => patchAccessRequestDraft(message.id, { suggestedApproverDisplayName: event.target.value })}
                                          placeholder="Optional"
                                        />
                                      </div>
                                      <div className="chat-access-request-field">
                                        <label htmlFor={`manager-email-${message.id}`}>Manager email</label>
                                        <input
                                          id={`manager-email-${message.id}`}
                                          className={accessRequestErrorsByMessageId[message.id]?.requesterManagerEmail ? "is-invalid" : ""}
                                          value={accessRequestDraftFor(message.id).requesterManagerEmail}
                                          onChange={(event) => patchAccessRequestDraft(message.id, { requesterManagerEmail: event.target.value })}
                                          placeholder="Optional"
                                        />
                                        {accessRequestErrorsByMessageId[message.id]?.requesterManagerEmail ? <span className="chat-access-request-error">{accessRequestErrorsByMessageId[message.id]?.requesterManagerEmail}</span> : null}
                                      </div>
                                      <div className="chat-access-request-field">
                                        <label htmlFor={`manager-name-${message.id}`}>Manager name</label>
                                        <input
                                          id={`manager-name-${message.id}`}
                                          value={accessRequestDraftFor(message.id).requesterManagerDisplayName}
                                          onChange={(event) => patchAccessRequestDraft(message.id, { requesterManagerDisplayName: event.target.value })}
                                          placeholder="Optional"
                                        />
                                      </div>
                                    </div>
                                    <div className="chat-access-request-field">
                                      <label htmlFor={`requester-comment-${message.id}`}>Extra context for admin</label>
                                      <textarea
                                        id={`requester-comment-${message.id}`}
                                        rows={2}
                                        value={accessRequestDraftFor(message.id).requesterComment}
                                        onChange={(event) => patchAccessRequestDraft(message.id, { requesterComment: event.target.value })}
                                        placeholder="Optional. Add urgency, project, customer, case, contract, or routing context"
                                      />
                                    </div>
                                    {accessRequestNoticeByMessageId[message.id] ? (
                                      <div className={`chat-access-request-notice is-${accessRequestNoticeByMessageId[message.id].tone}`}>
                                        {accessRequestNoticeByMessageId[message.id].text}
                                      </div>
                                    ) : null}
                                    <div className="chat-access-request-actions">
                                      <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => submitMissingSource(message)}>
                                        Send Hint Only
                                      </button>
                                      <button
                                        type="button"
                                        className="stitch-button stitch-button-primary stitch-button-small"
                                        onClick={() => submitAccessRequest(message)}
                                        disabled={Boolean(submittingAccessRequestByMessageId[message.id])}
                                      >
                                        {submittingAccessRequestByMessageId[message.id] ? "Submitting..." : "Request Access"}
                                      </button>
                                    </div>
                                  </div>
                                        </div>
                                      </div>
                                    ) : null}
                                  </>
                                ) : null}
                              </div>
                            ) : null}
                            {message.citations?.length ? (
                              <div className="chat-citation-row">
                                {groupCitationsBySource(message.citations).map((group) => (
                                  <button
                                    key={group.key}
                                    type="button"
                                    className="chat-citation-pill"
                                    title={group.rep.file_name}
                                    onClick={() => selectCitation(message.id, group.rep.citation_id)}
                                    onMouseEnter={() => setHoveredCitationId(group.rep.citation_id)}
                                    onMouseLeave={() => setHoveredCitationId(null)}
                                  >
                                    <MaterialIcon name={sourceIcon(group.rep.source_type).icon} />
                                    <span className="chat-citation-pill-name">{group.rep.file_name}</span>
                                    {group.items.length > 1 ? <span className="chat-citation-pill-count">{group.items.length}</span> : null}
                                  </button>
                                ))}
                              </div>
                            ) : null}
                          </>
                        )}
                      </article>
                      <div className="chat-feedback-row">
                        <button
                          type="button"
                          aria-label="Helpful"
                          className={`chat-feedback-button ${feedbackByMessageId[message.id] === "up" ? "is-active" : ""}`}
                          onClick={() => setFeedback(message, "up")}
                        >
                          <MaterialIcon name="thumb_up" />
                        </button>
                        <button
                          type="button"
                          aria-label="Not helpful"
                          className={`chat-feedback-button ${feedbackByMessageId[message.id] === "down" ? "is-active" : ""}`}
                          onClick={() => setFeedback(message, "down")}
                        >
                          <MaterialIcon name="thumb_down" />
                        </button>
                        <div className="chat-feedback-divider" />
                        <div className="chat-answer-actions">
                          <button
                            type="button"
                            className={`chat-feedback-button chat-answer-actions-trigger ${answerActionDraftFor(message.id).menuOpen ? "is-active" : ""}`}
                            aria-label="Answer actions"
                            aria-haspopup="menu"
                            aria-expanded={answerActionDraftFor(message.id).menuOpen}
                            onClick={() => openAnswerActionMenu(message.id)}
                          >
                            <MaterialIcon name="more_horiz" />
                          </button>
                          {answerActionDraftFor(message.id).menuOpen ? (
                            <div
                              className="chat-answer-actions-menu"
                              role="menu"
                              onMouseEnter={() => {
                                answerActionMenuHoldRef.current = message.id;
                                clearAnswerActionMenuTimer();
                              }}
                              onMouseLeave={() => {
                                answerActionMenuHoldRef.current = null;
                                scheduleAnswerActionMenuClose(message.id);
                              }}
                              onFocus={() => {
                                answerActionMenuHoldRef.current = message.id;
                                clearAnswerActionMenuTimer();
                              }}
                              onBlur={(event) => {
                                if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
                                  return;
                                }
                                answerActionMenuHoldRef.current = null;
                                scheduleAnswerActionMenuClose(message.id);
                              }}
                            >
                              <button
                                type="button"
                                role="menuitem"
                                disabled={isStreaming || answerActionDraftFor(message.id).redoSubmitting}
                                onClick={() => {
                                  clearAnswerActionMenuTimer();
                                  retryAnswer(message, "try_again");
                                }}
                              >
                                <MaterialIcon name="sync" />
                                Try again
                              </button>
                              <button
                                type="button"
                                role="menuitem"
                                disabled={answerActionDraftFor(message.id).redoSubmitting}
                                onClick={() => {
                                  clearAnswerActionMenuTimer();
                                  patchAnswerActionDraft(message.id, { menuOpen: false, redoOpen: true });
                                }}
                              >
                                <MaterialIcon name="tune" />
                                Add details
                              </button>
                            </div>
                          ) : null}
                        </div>
                        <button type="button" className="chat-copy-button" onClick={() => copyAnswer(message)} disabled={!message.content}>
                          <MaterialIcon name="content_copy" />
                          Copy Answer
                        </button>
                        {actionFlashByMessageId[message.id] ? <span className="chat-action-flash">{actionFlashByMessageId[message.id]}</span> : null}
                      </div>
                      {negativeFeedbackDraftFor(message.id).isOpen ? (
                        <div className="chat-negative-feedback-form">
                          <Field label="What went wrong?">
                            <Select
                              value={negativeFeedbackDraftFor(message.id).reason}
                              onChange={(event) =>
                                patchNegativeFeedbackDraft(message.id, { reason: event.target.value as NegativeFeedbackReason })
                              }
                            >
                              <option value="">Select a reason</option>
                              {NEGATIVE_FEEDBACK_REASONS.map((reason) => (
                                <option key={reason.value} value={reason.value}>{reason.label}</option>
                              ))}
                            </Select>
                          </Field>
                          <Field label="Optional note">
                            <Textarea
                              rows={2}
                              value={negativeFeedbackDraftFor(message.id).note}
                              onChange={(event) => patchNegativeFeedbackDraft(message.id, { note: event.target.value })}
                              placeholder="Add context for the operator reviewing this answer"
                            />
                          </Field>
                          <div className="toolbar-inline">
                            <button
                              type="button"
                              className="stitch-button stitch-button-primary"
                              disabled={negativeFeedbackDraftFor(message.id).isSubmitting}
                              onClick={() => submitNegativeFeedback(message)}
                            >
                              {negativeFeedbackDraftFor(message.id).isSubmitting ? "Submitting" : "Submit issue"}
                            </button>
                            <button
                              type="button"
                              className="stitch-button stitch-button-secondary"
                              onClick={() => patchNegativeFeedbackDraft(message.id, { isOpen: false, isSubmitting: false })}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {answerActionDraftFor(message.id).redoOpen ? (
                        <div className="chat-redo-form">
                          <Field label="Search mode">
                            <Select
                              value={answerActionDraftFor(message.id).redoMode}
                              onChange={(event) => {
                                const redoMode = event.target.value as AnswerActionDraft["redoMode"];
                                patchAnswerActionDraft(message.id, { redoMode, ...(redoMode === "keyword" ? { redoDepth: "fast" } : {}) });
                              }}
                            >
                              <option value="auto">Auto</option>
                              <option value="hybrid">Hybrid</option>
                              <option value="keyword">Keyword</option>
                              <option value="vector">Semantic</option>
                            </Select>
                          </Field>
                          <Field label="Depth" help={answerActionDraftFor(message.id).redoMode === "keyword" ? "Keyword retry runs fast exact search in this version." : undefined}>
                            <Select
                              value={answerActionDraftFor(message.id).redoMode === "keyword" ? "fast" : answerActionDraftFor(message.id).redoDepth}
                              disabled={answerActionDraftFor(message.id).redoMode === "keyword"}
                              onChange={(event) =>
                                patchAnswerActionDraft(message.id, { redoDepth: event.target.value as AnswerActionDraft["redoDepth"] })
                              }
                            >
                              <option value="fast">Fast</option>
                              <option value="strict">Strict</option>
                            </Select>
                          </Field>
                          <div className="toolbar-inline">
                            <Toggle
                              checked={answerActionDraftFor(message.id).includeDocuments}
                              onChange={(event) => patchAnswerActionDraft(message.id, { includeDocuments: event.target.checked })}
                              label="Documents"
                            />
                            <Toggle
                              checked={answerActionDraftFor(message.id).includeTables}
                              onChange={(event) => patchAnswerActionDraft(message.id, { includeTables: event.target.checked })}
                              label="Spreadsheets"
                            />
                            <Toggle
                              checked={answerActionDraftFor(message.id).includeEmails}
                              onChange={(event) => patchAnswerActionDraft(message.id, { includeEmails: event.target.checked })}
                              label="Emails"
                            />
                          </div>
                          <Field label="Search instruction">
                            <Textarea
                              rows={2}
                              value={answerActionDraftFor(message.id).redoNote}
                              onChange={(event) => patchAnswerActionDraft(message.id, { redoNote: event.target.value })}
                              placeholder="Optional: use exact wording, focus on a file, or name missing context"
                            />
                          </Field>
                          <div className="toolbar-inline">
                            <button
                              type="button"
                              className="stitch-button stitch-button-primary"
                              disabled={answerActionDraftFor(message.id).redoSubmitting || isStreaming}
                              onClick={() => retryAnswer(message, "add_details")}
                            >
                              {answerActionDraftFor(message.id).redoSubmitting ? "Retrying" : "Redo search"}
                            </button>
                            <button
                              type="button"
                              className="stitch-button stitch-button-secondary"
                              disabled={answerActionDraftFor(message.id).redoSubmitting}
                              onClick={() => patchAnswerActionDraft(message.id, { redoOpen: false })}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ),
              )
            ) : (
              <div className="chat-empty-state">
                <div className="chat-empty-card">
                  <span className="chat-empty-kicker">Grounded Workspace</span>
                  <h2>Ask your first question to start a thread.</h2>
                  <p>Threads persist in this browser, and grounded evidence appears on the right as soon as retrieval returns usable citations.</p>
                  <div className="chat-empty-list">
                    <span>1. Upload a file or confirm one is already visible in My Sources.</span>
                    <span>2. Wait until the file shows as indexed and ready for retrieval.</span>
                    <span>3. Ask here and watch retrieval, grounding, and answer generation complete in order.</span>
                  </div>
                  <div className="chat-empty-actions">
                    <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={() => router.push("/console/workspace/uploads")}>
                      Upload documents
                    </button>
                    <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => router.push("/console/workspace/sources")}>
                      Open My Sources
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="chat-composer-wrap">
            <div className="chat-composer">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    if (!isStreaming) submitQuestion();
                  }
                }}
                placeholder="Ask follow up questions or upload new sources..."
                aria-label="Ask a question"
                rows={3}
              />
              <div className="chat-composer-footer">
                <div className="chat-composer-tools">
                  <button type="button" className="is-coming-soon" aria-label="Attach file (coming soon)" disabled title={COMING_SOON_TITLE}>
                    <MaterialIcon name="attach_file" />
                  </button>
                  <button type="button" className="is-coming-soon" aria-label="Image query (coming soon)" disabled title={COMING_SOON_TITLE}>
                    <MaterialIcon name="image" />
                  </button>
                  <button type="button" className="is-coming-soon" aria-label="Voice capture (coming soon)" disabled title={COMING_SOON_TITLE}>
                    <MaterialIcon name="mic" />
                  </button>
                </div>
                <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={submitQuestion} disabled={isStreaming}>
                  {isStreaming ? "Working..." : "Ask"}
                  <MaterialIcon name="send" />
                </button>
              </div>
            </div>
            <p className="chat-disclaimer">AI can make mistakes. Verify critical answers against the cited source context.</p>
          </div>
        </main>

        <aside className="chat-evidence-panel">
          <div className="chat-evidence-head">
            <h3>Retrieved Sources</h3>
            <span>{totalEvidenceCount} Citations</span>
          </div>
          <div className="chat-evidence-list">
            {showEvidence ? evidenceSections.map((section, index) => {
              const isCollapsed = collapsedEvidenceSections[section.id] ?? section.id !== activeEvidenceSection?.id;
              const isSelectedSection = activeEvidenceSection?.id === section.id;
              return (
                <section key={section.id} className={`chat-evidence-group ${isSelectedSection ? "is-active-group" : ""}`}>
                  <button
                    type="button"
                    className="chat-evidence-group-toggle"
                    ref={(node) => {
                      evidenceSectionRefs.current[section.id] = node;
                    }}
                    onClick={() => {
                      setSelectedEvidenceMessageId(section.id);
                      setCollapsedEvidenceSections((current) => ({ ...current, [section.id]: !isCollapsed }));
                    }}
                  >
                    <div>
                      <strong>{`Q${index + 1}. ${section.label}`}</strong>
                      <span>{section.citations.length ? `${section.citations.length} retrieved source${section.citations.length === 1 ? "" : "s"}` : "No retrieved sources"}</span>
                    </div>
                    <span className="chat-evidence-group-symbol" aria-hidden="true">{isCollapsed ? "+" : "-"}</span>
                  </button>
                  {!isCollapsed ? (
                    <div className="chat-evidence-group-body">
                      {section.citations.length ? groupCitationsBySource(section.citations).map((group) => {
                        const citation = group.rep;
                        const iconData = sourceIcon(citation.source_type);
                        const groupIds = new Set(group.items.map((item) => item.citation_id));
                        const isSelected = isSelectedSection && selectedCitationId !== null && groupIds.has(selectedCitationId);
                        const isHovered = hoveredCitationId !== null && groupIds.has(hoveredCitationId);
                        const selectedInGroup = group.items.find((item) => item.citation_id === selectedCitationId);
                        const shown = selectedInGroup ?? citation;
                        return (
                          <button
                            key={group.key}
                            type="button"
                            className={`chat-evidence-card ${isSelected ? "is-selected" : ""} ${isHovered ? "is-hovered" : ""}`.trim()}
                            onClick={() => selectCitation(section.id, shown.citation_id)}
                          >
                            <div className="chat-evidence-card-head">
                              <div className={`chat-evidence-icon ${iconData.tone}`}>
                                <MaterialIcon name={iconData.icon} />
                              </div>
                              <div>
                                <strong className="chat-evidence-filename" title={citation.file_name}>{citation.file_name}</strong>
                                <span>{shown.locator || shown.heading}{group.items.length > 1 ? ` · ${group.items.length} passages` : ""}</span>
                                {citation.freshness ? (
                                  <span className={`badge ${citation.freshness.status === "fresh" ? "is-good" : citation.freshness.status === "stale" ? "is-danger" : "is-warning"}`}>
                                    {citation.freshness.status}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <div className="chat-evidence-snippet">{shown.snippet}</div>
                          </button>
                        );
                      }) : (
                        <div className="chat-evidence-empty-inline">
                          <strong>No matching evidence for this answer.</strong>
                        </div>
                      )}
                    </div>
                  ) : null}
                </section>
              );
            }) : (
              <div className="chat-evidence-empty">
                <MaterialIcon name="database" />
                <strong>{isNoContextMessage(latestAssistantMessage) ? "No matching evidence found." : "No retrieved sources yet."}</strong>
                <p>
                  {isNoContextMessage(latestAssistantMessage)
                    ? "Retrieval finished but found no usable indexed match in the sources visible to your account. Try exact wording from the document or confirm that indexing completed."
                    : "Ask your first question and the live backend citations will appear here. If you just uploaded a file, wait until My Sources marks it as indexed first."}
                </p>
                {!isNoContextMessage(latestAssistantMessage) ? (
                  <div className="chat-evidence-empty-actions">
                    <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={() => router.push("/console/workspace/uploads")}>
                      Check uploads
                    </button>
                  </div>
                ) : null}
              </div>
            )}
            {selectedCitation ? (
              <div className="chat-context-card">
                <div className="chat-context-head">
                  <div>
                    <strong>{contextTitleLabel}</strong>
                    {contextLocator ? <span>{contextLocator}</span> : null}
                    {citationContext?.freshness ? (
                      <span className={`badge ${citationContext.freshness.status === "fresh" ? "is-good" : citationContext.freshness.status === "stale" ? "is-danger" : "is-warning"}`}>
                        {citationContext.freshness.status}
                      </span>
                    ) : null}
                  </div>
                </div>
                <a className="chat-context-link" href={browserApiUrl(`/corpus/${selectedCitation.source_id}/file`)} target="_blank" rel="noreferrer">
                  Open {contextTitleLabel}
                </a>
                {citationContextError ? <p>{citationContextError}</p> : null}
                {!citationContext && !citationContextError ? <p>Loading chunk context...</p> : null}
                {citationContext?.target ? (
                  <>
                    <p>{citationContext.target.chunk_text}</p>
                    {citationContext.neighbors.length ? (
                      <div className="chat-context-neighbors">
                        {citationContext.neighbors.map((item) => (
                          <div key={item.id} className="chat-context-neighbor">
                            <strong>{item.heading || `Chunk ${item.chunk_index}`}</strong>
                            <span>{item.chunk_text}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="chat-evidence-footer">
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-block is-coming-soon" disabled aria-label="Export findings (coming soon)" title={COMING_SOON_TITLE}>
              <MaterialIcon name="open_in_new" />
              Export Findings
              <span className="coming-soon-badge">Soon</span>
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
