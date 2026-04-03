"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { browserApiUrl, browserFetch } from "@/lib/api-browser";
import type { AskResponse, SearchResponse } from "@/lib/types";
import { readThreads, ThreadMessage, ThreadRecord, writeThreads } from "@/lib/workspace";

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

function toTitle(input: string) {
  const cleaned = input.trim().replace(/\s+/g, " ");
  return cleaned.length > 40 ? `${cleaned.slice(0, 37)}...` : cleaned;
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

export function ChatWorkspace({ initialThreadId }: { initialThreadId?: string }) {
  const router = useRouter();
  const [threads, setThreads] = useState<ThreadRecord[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState(initialThreadId || "");
  const [hydrated, setHydrated] = useState(false);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [deepResearch, setDeepResearch] = useState(false);
  const [searchSummary, setSearchSummary] = useState<SearchResponse | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);

  useEffect(() => {
    const stored = readThreads();
    setThreads(stored);
    setHydrated(true);
    if (initialThreadId) {
      setCurrentThreadId(initialThreadId);
      return;
    }
    if (stored[0]) {
      setCurrentThreadId(stored[0].id);
    }
  }, [initialThreadId]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    writeThreads(threads);
  }, [hydrated, threads]);

  const activeThread = useMemo(() => threads.find((item) => item.id === currentThreadId) || null, [threads, currentThreadId]);
  const assistantMessages = useMemo(
    () => (activeThread?.messages || []).filter((message) => message.role === "assistant"),
    [activeThread],
  );
  const activeCitations = useMemo(() => assistantMessages.at(-1)?.citations || [], [assistantMessages]);
  const selectedCitation = activeCitations.find((item) => item.citation_id === selectedCitationId) || activeCitations[0] || null;
  const hasConversation = Boolean(activeThread?.messages.length);
  const showEvidence = hasConversation && activeCitations.length > 0;

  useEffect(() => {
    setSelectedCitationId(activeCitations[0]?.citation_id || null);
  }, [currentThreadId, activeCitations]);

  async function submitQuestion() {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) {
      return;
    }

    setError("");
    setIsStreaming(true);
    const threadId = activeThread?.id || createId();
    const existingMessages = activeThread?.messages || [];
    const userMessage: ThreadMessage = {
      id: createId(),
      role: "user",
      content: trimmed,
    };
    const nextThread: ThreadRecord = {
      id: threadId,
      title: activeThread?.title || toTitle(trimmed),
      createdAt: activeThread?.createdAt || new Date().toISOString(),
      messages: [...existingMessages, userMessage],
    };

    setThreads((prev) => [nextThread, ...prev.filter((item) => item.id !== threadId)]);
    setCurrentThreadId(threadId);
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
          const event = JSON.parse(line) as { type: string; result?: AskResponse };
          if (event.type === "result" && event.result) {
            finalResult = event.result;
          }
        }
      }

      if (!finalResult) {
        throw new Error("No final result returned by /ask/stream.");
      }

      const assistantMessage: ThreadMessage = {
        id: createId(),
        role: "assistant",
        content: finalResult.answer || "No answer returned.",
        citations: finalResult.citations,
        mode: finalResult.mode,
        debugInfo: finalResult.debug_info,
      };

      setThreads((prev) =>
        prev.map((item) =>
          item.id === threadId
            ? { ...item, messages: [...item.messages, assistantMessage] }
            : item,
        ),
      );
      setSearchSummary(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workspace request failed.");
    } finally {
      setIsStreaming(false);
    }
  }

  function startFreshThread() {
    setCurrentThreadId("");
    setQuestion("");
    setSearchSummary(null);
    setSelectedCitationId(null);
    router.push("/console/workspace/chat");
  }

  return (
    <div className="chat-page">
      {hasConversation ? (
        <div className="chat-metadata-bar">
          <div className="chat-mode-pill">
            <span className="material-symbols-outlined icon-fill">bolt</span>
            {mode === "hybrid" ? "Hybrid Search" : mode}
          </div>
          <div>Latency: <strong>{searchSummary?.latency_ms ? `${searchSummary.latency_ms}ms` : "Captured"}</strong></div>
          <div>Sources: <strong>{activeCitations.length}</strong></div>
          <div>Corpus: <strong>{selectedCitation?.file_name ? "Retrieved Evidence" : "Grounded Search"}</strong></div>
          <div className="chat-speed-toggle">
            <button type="button" className={!deepResearch ? "is-active" : ""} onClick={() => setDeepResearch(false)}>
              Fast
            </button>
            <button type="button" className={deepResearch ? "is-active" : ""} onClick={() => setDeepResearch(true)}>
              Strict
            </button>
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
                      <article className="chat-answer-card">
                        <h3>{activeThread.title || "Grounded Answer"}</h3>
                        {message.content.split(/\n+/).map((paragraph, index) => (
                          <p key={`${message.id}-${index}`}>{paragraph}</p>
                        ))}
                        {message.citations?.length ? (
                          <div className="chat-citation-row">
                            {message.citations.map((citation) => (
                              <button
                                key={citation.citation_id}
                                type="button"
                                className="chat-citation-pill"
                                onClick={() => setSelectedCitationId(citation.citation_id)}
                              >
                                <span className="material-symbols-outlined">
                                  {sourceIcon(citation.source_type).icon}
                                </span>
                                {citation.file_name}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </article>
                      <div className="chat-feedback-row">
                        <button type="button" aria-label="Helpful">
                          <span className="material-symbols-outlined">thumb_up</span>
                        </button>
                        <button type="button" aria-label="Not helpful">
                          <span className="material-symbols-outlined">thumb_down</span>
                        </button>
                        <div className="chat-feedback-divider" />
                        <button type="button" className="chat-copy-button">
                          <span className="material-symbols-outlined">content_copy</span>
                          Copy Answer
                        </button>
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
                  <p>Retrieved sources appear only after the first live backend answer is returned with citations.</p>
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
                  <button type="button" aria-label="Attach">
                    <span className="material-symbols-outlined">attach_file</span>
                  </button>
                  <button type="button" aria-label="Image">
                    <span className="material-symbols-outlined">image</span>
                  </button>
                  <button type="button" aria-label="Microphone">
                    <span className="material-symbols-outlined">mic</span>
                  </button>
                </div>
                <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={submitQuestion} disabled={isStreaming}>
                  {isStreaming ? "Thinking..." : "Ask"}
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
            </div>
            <p className="chat-disclaimer">AI can make mistakes. Verify critical HR data with your department head.</p>
          </div>
        </main>

        <aside className="chat-evidence-panel">
          <div className="chat-evidence-head">
            <h3>Retrieved Sources</h3>
            <span>{activeCitations.length || 3} Citations</span>
          </div>
          <div className="chat-evidence-list">
            {showEvidence ? activeCitations.map((citation) => {
              const iconData = sourceIcon(citation.source_type);
              return (
                <button
                  key={citation.citation_id}
                  type="button"
                  className={`chat-evidence-card ${selectedCitation?.citation_id === citation.citation_id ? "is-selected" : ""}`}
                  onClick={() => setSelectedCitationId(citation.citation_id)}
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
              <div className="chat-evidence-empty">
                <span className="material-symbols-outlined">database</span>
                <strong>No retrieved sources yet.</strong>
                <p>Ask your first question and the live backend citations will appear here.</p>
              </div>
            )}
          </div>
          <div className="chat-evidence-footer">
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-block">
              <span className="material-symbols-outlined">open_in_new</span>
              Export Findings
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
