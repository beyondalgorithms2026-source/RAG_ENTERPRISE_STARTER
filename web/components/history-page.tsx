"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { readThreads, ThreadRecord, THREADS_UPDATED_EVENT } from "@/lib/workspace";

function lastUpdated(thread: ThreadRecord) {
  return new Date(thread.createdAt).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function answerCount(thread: ThreadRecord) {
  return thread.messages.filter((message) => message.role === "assistant").length;
}

export function HistoryPage() {
  const [threads, setThreads] = useState<ThreadRecord[]>([]);

  useEffect(() => {
    function refresh() {
      setThreads(readThreads());
    }

    refresh();
    window.addEventListener(THREADS_UPDATED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(THREADS_UPDATED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  return (
    <div className="history-page">
      <div className="history-header">
        <div>
          <h1>Search History</h1>
          <p>Your first question becomes the saved thread title. This history persists in the current browser so reloads reopen the same stitched threads.</p>
        </div>
      </div>

      <section className="history-list">
        {threads.length === 0 ? (
          <div className="history-empty-card">
            <span className="material-symbols-outlined">history</span>
            <strong>No chat history yet.</strong>
            <p>Ask your first grounded question in Chat and it will appear here.</p>
          </div>
        ) : (
          threads.map((thread) => (
            <Link key={thread.id} href={`/console/workspace/chat/${thread.id}`} className="history-thread-card">
              <div className="history-thread-head">
                <span className="material-symbols-outlined">forum</span>
                <div>
                  <strong>{thread.title}</strong>
                  <span>Updated {lastUpdated(thread)}</span>
                </div>
              </div>
              <p>{thread.messages[0]?.content || "Conversation thread"}</p>
              <div className="history-thread-meta">
                <span>{thread.messages.length} messages</span>
                <span>{answerCount(thread)} answers</span>
                <span>Open thread</span>
              </div>
            </Link>
          ))
        )}
      </section>
    </div>
  );
}
