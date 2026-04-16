"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";
import type { AskResponse, SearchResponse } from "@/lib/types";
import { readThreads, THREADS_UPDATED_EVENT, ThreadMessage, ThreadRecord, updateThreadRecord, upsertThreadRecord } from "@/lib/workspace";

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
};

type EvidenceSection = {
  id: string;
  answer: ThreadMessage;
  question: string;
  label: string;
  citations: NonNullable<ThreadMessage["citations"]>;
};

type FeedbackState = "up" | "down" | null;

type StoredEvidenceRailState = {
  selectedEvidenceMessageId: string | null;
  selectedCitationId: string | null;
  collapsedEvidenceSections: Record<string, boolean>;
};

const EVIDENCE_RAIL_STORAGE_KEY = "rag_console_evidence_rail_v1";

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

function formatSourceTitle(fileName: string) {
  const trimmed = fileName.trim();
  return trimmed.replace(/\.(pdf|docx|doc|txt|md|pptx|xlsx|csv)$/i, "") || trimmed;
}

function isNoContextMessage(message: ThreadMessage | null | undefined) {
  return (message?.content || "").trim() === "Not found in provided sources.";
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
  const [threads, setThreads] = useState<ThreadRecord[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState(initialThreadId || "");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [deepResearch, setDeepResearch] = useState(false);
  const [searchSummary, setSearchSummary] = useState<SearchResponse | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [selectedEvidenceMessageId, setSelectedEvidenceMessageId] = useState<string | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [citationContext, setCitationContext] = useState<CitationContextResponse | null>(null);
  const [citationContextError, setCitationContextError] = useState("");
  const [collapsedEvidenceSections, setCollapsedEvidenceSections] = useState<Record<string, boolean>>({});
  const [feedbackByMessageId, setFeedbackByMessageId] = useState<Record<string, FeedbackState>>({});
  const [actionFlashByMessageId, setActionFlashByMessageId] = useState<Record<string, string>>({});
  const evidenceSectionRefs = useRef<Record<string, HTMLElement | null>>({});

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
  const activeRetrievalPath =
    String(
      (searchSummary?.debug_info as { retrieval_path_used?: string } | undefined)?.retrieval_path_used ||
      (latestAssistantMessage?.debugInfo as { retrieval_path_used?: string } | undefined)?.retrieval_path_used ||
      "hybrid",
    );

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

  function syncThreads(nextThreads: ThreadRecord[]) {
    setThreads(nextThreads);
  }

  function patchThread(threadId: string, updater: (thread: ThreadRecord) => ThreadRecord) {
    const nextThreads = updateThreadRecord(threadId, updater);
    setThreads(nextThreads);
  }

  async function submitQuestion() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) {
      return;
    }

    setError("");
    setSearchSummary(null);
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
      const search = await browserFetch<SearchResponse>("/search", {
        method: "POST",
        json: { question: trimmed, k: 6, mode, debug: true, deep_research: deepResearch },
      });
      setSearchSummary(search);

      const response = await fetch(browserApiUrl("/ask/stream"), {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          k_chunks: 6,
          mode,
          deep_research: deepResearch,
          dry_run: false,
        }),
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

      patchThread(threadId, (thread) => ({
        ...thread,
        messages: thread.messages.map((message) =>
          message.id === placeholderId
            ? {
                ...message,
                status: "completed",
                content: finalResult.answer || "No answer returned.",
                citations: finalResult.citations,
                mode: finalResult.mode,
                debugInfo: finalResult.debug_info,
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
    setSearchSummary(null);
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

  function setFeedback(messageId: string, feedback: Exclude<FeedbackState, null>) {
    setFeedbackByMessageId((current) => {
      const nextValue = current[messageId] === feedback ? null : feedback;
      return { ...current, [messageId]: nextValue };
    });
    flashAction(messageId, feedback === "up" ? "Marked helpful" : "Marked not helpful");
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

  const contextLocator = buildLocatorSummary(
    safeJsonParse(citationContext?.target?.locator_json),
    citationContext?.target?.heading || selectedCitation?.heading || null,
    citationContext?.target?.chunk_index ?? null,
  );
  const contextTitle = citationContext?.source_file_name || selectedCitation?.file_name || "Retrieved source";
  const contextTitleLabel = formatSourceTitle(contextTitle);

  return (
    <div className="chat-page">
      {hasConversation ? (
        <div className="chat-metadata-bar">
          <div className="chat-mode-pill">
            <span className="material-symbols-outlined icon-fill">bolt</span>
            {mode === "hybrid" ? "Hybrid Search" : mode}
          </div>
          <div>Latency: <strong>{searchSummary?.latency_ms ? `${searchSummary.latency_ms}ms` : "Captured"}</strong></div>
          <div>Sources: <strong>{activeEvidenceSection?.citations.length || 0}</strong></div>
          <div>Path: <strong>{activeRetrievalPath}</strong></div>
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
        </div>
      ) : null}

      <div className="chat-layout">
        <main className="chat-main">
          <div className="chat-scroll">
            <div className="chat-utility-row">
              <button type="button" className="chat-new-thread" onClick={startFreshThread}>
                <span className="material-symbols-outlined icon-fill">auto_awesome</span>
              </button>
              {error ? <div className="chat-error-banner">{error}</div> : null}
            </div>

            {activeThread?.messages.length ? (
              activeThread.messages.map((message) =>
                message.role === "user" ? (
                  <div key={message.id} className="chat-user-row">
                    <div className="chat-user-bubble">{message.content}</div>
                  </div>
                ) : (
                  <div key={message.id} className="chat-answer-row">
                    <div className="chat-answer-avatar">
                      <span className="material-symbols-outlined icon-fill">auto_awesome</span>
                    </div>
                    <div className="chat-answer-column">
                      <article className={`chat-answer-card ${message.status === "pending" ? "is-pending" : ""} ${message.status === "failed" ? "is-failed" : ""}`}>
                        {message.status === "pending" ? (
                          <div className="chat-progress-card">
                            <div className="chat-progress-head">
                              <strong>{message.progressLabel || "Working on your answer"}</strong>
                              <span>{message.progress || 0}%</span>
                            </div>
                            <div className="chat-progress-bar">
                              <div style={{ width: `${message.progress || 0}%` }} />
                            </div>
                            <p className="chat-progress-copy">{describeAskProgress(message.progressLabel)}</p>
                          </div>
                        ) : (
                          <>
                            {message.content.split(/\n+/).filter(Boolean).map((paragraph, index) => (
                              <p key={`${message.id}-${index}`}>{paragraph}</p>
                            ))}
                            {isNoContextMessage(message) ? (
                              <div className="chat-no-context-card">
                                <strong>No grounded evidence was retrieved for this question.</strong>
                                <p>Try exact wording from the source, confirm the file finished indexing, or check My Sources to verify that the document is visible to your current account.</p>
                              </div>
                            ) : null}
                            {message.citations?.length ? (
                              <div className="chat-citation-row">
                                {message.citations.map((citation) => (
                                  <button
                                    key={citation.citation_id}
                                    type="button"
                                    className="chat-citation-pill"
                                    onClick={() => {
                                      setSelectedEvidenceMessageId(message.id);
                                      setSelectedCitationId(citation.citation_id);
                                      setCollapsedEvidenceSections((current) => ({ ...current, [message.id]: false }));
                                      window.setTimeout(() => {
                                        evidenceSectionRefs.current[message.id]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
                                      }, 0);
                                    }}
                                  >
                                    <span className="material-symbols-outlined">
                                      {sourceIcon(citation.source_type).icon}
                                    </span>
                                    {citation.file_name}
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
                          onClick={() => setFeedback(message.id, "up")}
                        >
                          <span className="material-symbols-outlined">thumb_up</span>
                        </button>
                        <button
                          type="button"
                          aria-label="Not helpful"
                          className={`chat-feedback-button ${feedbackByMessageId[message.id] === "down" ? "is-active" : ""}`}
                          onClick={() => setFeedback(message.id, "down")}
                        >
                          <span className="material-symbols-outlined">thumb_down</span>
                        </button>
                        <div className="chat-feedback-divider" />
                        <button type="button" className="chat-copy-button" onClick={() => copyAnswer(message)} disabled={!message.content}>
                          <span className="material-symbols-outlined">content_copy</span>
                          Copy Answer
                        </button>
                        {actionFlashByMessageId[message.id] ? <span className="chat-action-flash">{actionFlashByMessageId[message.id]}</span> : null}
                      </div>
                    </div>
                  </div>
                ),
              )
            ) : (
              <div className="chat-empty-state">
                <div className="chat-empty-card">
                  <span className="chat-empty-kicker">Grounded Workspace</span>
                  <h2>Ask your first question to start a stitched thread.</h2>
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
                placeholder="Ask follow up questions or upload new sources..."
                rows={3}
              />
              <div className="chat-composer-footer">
                <div className="chat-composer-tools">
                  <button type="button" aria-label="Attach" disabled title="File attach from chat is not live yet. Use Upload Documents.">
                    <span className="material-symbols-outlined">attach_file</span>
                  </button>
                  <button type="button" aria-label="Image" disabled title="Image query input is not live yet.">
                    <span className="material-symbols-outlined">image</span>
                  </button>
                  <button type="button" aria-label="Microphone" disabled title="Voice capture is not live yet.">
                    <span className="material-symbols-outlined">mic</span>
                  </button>
                </div>
                <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={submitQuestion} disabled={isStreaming}>
                  {isStreaming ? "Working..." : "Ask"}
                  <span className="material-symbols-outlined">send</span>
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
                      {section.citations.length ? section.citations.map((citation) => {
                        const iconData = sourceIcon(citation.source_type);
                        const isSelected = isSelectedSection && selectedCitation?.citation_id === citation.citation_id;
                        return (
                          <button
                            key={citation.citation_id}
                            type="button"
                            className={`chat-evidence-card ${isSelected ? "is-selected" : ""}`}
                            onClick={() => {
                              setSelectedEvidenceMessageId(section.id);
                              setSelectedCitationId(citation.citation_id);
                              setCollapsedEvidenceSections((current) => ({ ...current, [section.id]: false }));
                              window.setTimeout(() => {
                                evidenceSectionRefs.current[section.id]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
                              }, 0);
                            }}
                          >
                            <div className="chat-evidence-card-head">
                              <div className={`chat-evidence-icon ${iconData.tone}`}>
                                <span className="material-symbols-outlined">{iconData.icon}</span>
                              </div>
                              <div>
                                <strong>{citation.file_name}</strong>
                                <span>{citation.locator || citation.heading}</span>
                              </div>
                            </div>
                            <div className="chat-evidence-snippet">{citation.snippet}</div>
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
                <span className="material-symbols-outlined">database</span>
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
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-block" disabled title="Export lands in a later milestone.">
              <span className="material-symbols-outlined">open_in_new</span>
              Export Findings
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
