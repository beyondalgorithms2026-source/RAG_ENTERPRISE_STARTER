"use client";

import Link from "next/link";
import { useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import type { SearchResponse } from "@/lib/types";

export function SearchWorkspace() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const hasSearched = result !== null;

  async function runSearch() {
    if (!query.trim()) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = await browserFetch<SearchResponse>("/search", {
        method: "POST",
        json: { question: query, k: 8, mode, debug: true },
      });
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="workspace-shell">
      <section className="workspace-panel">
        <div className="workspace-title">Enterprise Search</div>
        <p className="muted-copy">Search across indexed corpora with grounded snippets before jumping into chat.</p>
        <div className="panel-toolbar" style={{ marginTop: 16 }}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search enterprise knowledge..." />
          <select value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="hybrid">Hybrid</option>
            <option value="vector">Semantic</option>
            <option value="keyword">Keyword</option>
          </select>
          <button className="button button-primary" type="button" onClick={runSearch} disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
        {error ? <div className="error-banner">{error}</div> : null}
      </section>
      <section className="inventory-table">
        {loading ? (
          <div className="workspace-empty-state">
            <div className="workspace-empty-card">
              <span className="material-symbols-outlined workspace-empty-icon">progress_activity</span>
              <h2>Searching indexed content...</h2>
              <p>Retrieval is running across the sources your account can currently access. Results appear here before you jump into chat.</p>
            </div>
          </div>
        ) : null}
        {!loading && !hasSearched ? (
          <div className="workspace-empty-state">
            <div className="workspace-empty-card">
              <span className="material-symbols-outlined workspace-empty-icon">manage_search</span>
              <h2>Search is ready for the first indexed source.</h2>
              <p>On a clean setup, upload one file first, wait for it to finish indexing, then search here to confirm retrieval before asking longer questions in chat.</p>
              <div className="workspace-empty-actions">
                <Link href="/console/workspace/uploads" className="stitch-button stitch-button-primary stitch-button-small">Upload first file</Link>
                <Link href="/console/workspace/chat" className="stitch-button stitch-button-secondary stitch-button-small">Open chat</Link>
              </div>
            </div>
          </div>
        ) : null}
        {!loading ? result?.results.map((item) => (
          <article className="inventory-row" key={`${item.chunk_id}-${item.source_id}`}>
            <div>
              <div className="inventory-title">{item.heading}</div>
              <div className="table-subtle">{item.file_name}</div>
            </div>
            <div>{item.source_type}</div>
            <div>{item.locator || "n/a"}</div>
            <div>{item.score.toFixed(3)}</div>
            <div>{item.snippet}</div>
          </article>
        )) : null}
        {!loading && result && result.results.length === 0 ? (
          <div className="workspace-empty-state">
            <div className="workspace-empty-card">
              <span className="material-symbols-outlined workspace-empty-icon">travel_explore</span>
              <h2>No matching evidence found.</h2>
              <p>The system finished retrieval but found no indexed match for this query in the sources visible to your account. If a file was uploaded recently, it may still be indexing or outside your current visibility scope.</p>
              <div className="workspace-empty-actions">
                <Link href="/console/workspace/sources" className="stitch-button stitch-button-secondary stitch-button-small">Check My Sources</Link>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
