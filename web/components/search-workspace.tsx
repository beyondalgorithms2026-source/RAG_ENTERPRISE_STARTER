"use client";

import { useState } from "react";

import { browserFetch } from "@/lib/api-browser";
import type { SearchResponse } from "@/lib/types";

export function SearchWorkspace() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
        {result?.results.map((item) => (
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
        ))}
        {result && result.results.length === 0 ? <div className="empty-state">No matching evidence found.</div> : null}
      </section>
    </div>
  );
}
