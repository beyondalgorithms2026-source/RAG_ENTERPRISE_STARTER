"use client";

import { MaterialIcon } from "@/components/icons";
import Link from "next/link";
import { useState } from "react";

import { Select } from "@/components/ui/Select";
import { TextInput } from "@/components/ui/TextInput";
import { browserFetch } from "@/lib/api-browser";
import type { SearchResponse } from "@/lib/types";

const MODE_LABELS: Record<string, string> = {
  hybrid: "Hybrid",
  vector: "Semantic",
  keyword: "Keyword",
};

function sourceGlyph(sourceType: string) {
  const value = sourceType.toLowerCase();
  if (value.includes("pdf")) return "picture_as_pdf";
  if (value.includes("doc") || value.includes("text") || value.includes("md")) return "description";
  return "link";
}

export function SearchWorkspace() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const hasSearched = result !== null;
  const results = result?.results ?? [];
  const maxScore = results.reduce((max, item) => Math.max(max, item.score), 0) || 1;
  const modeLabel = MODE_LABELS[result?.mode ?? mode] ?? (result?.mode ?? mode);

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
    <div className="search-page">
      <section className="search-header">
        <div className="search-header-copy">
          <h1>Enterprise Search</h1>
          <p>Search across indexed corpora with grounded snippets before jumping into chat.</p>
        </div>
        <div className="search-toolbar">
          <TextInput
            className="search-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") runSearch();
            }}
            placeholder="Search enterprise knowledge..."
            aria-label="Search query"
          />
          <Select
            className="search-mode"
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            aria-label="Retrieval mode"
          >
            <option value="hybrid">Hybrid</option>
            <option value="vector">Semantic</option>
            <option value="keyword">Keyword</option>
          </Select>
          <button className="stitch-button stitch-button-primary stitch-button-small" type="button" onClick={runSearch} disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
        {error ? <div className="error-banner">{error}</div> : null}
        {!loading && hasSearched && results.length > 0 ? (
          <div className="search-result-summary">
            <strong>{results.length}</strong> result{results.length === 1 ? "" : "s"} · {modeLabel} retrieval
            {typeof result?.latency_ms === "number" ? <span> · {Math.round(result.latency_ms)}ms</span> : null}
          </div>
        ) : null}
      </section>

      {loading ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-card">
            <MaterialIcon name="progress_activity" className="workspace-empty-icon" />
            <h2>Searching indexed content...</h2>
            <p>Retrieval is running across the sources your account can currently access. Results appear here before you jump into chat.</p>
          </div>
        </div>
      ) : null}

      {!loading && !hasSearched ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-card">
            <MaterialIcon name="manage_search" className="workspace-empty-icon" />
            <h2>Search is ready for the first indexed source.</h2>
            <p>On a clean setup, upload one file first, wait for it to finish indexing, then search here to confirm retrieval before asking longer questions in chat.</p>
            <div className="workspace-empty-actions">
              <Link href="/console/workspace/uploads" className="stitch-button stitch-button-primary stitch-button-small">Upload first file</Link>
              <Link href="/console/workspace/chat" className="stitch-button stitch-button-secondary stitch-button-small">Open chat</Link>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && results.length > 0 ? (
        <div className="admin-table-scroll">
          <table className="admin-data-table">
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Type</th>
                <th scope="col">Location</th>
                <th scope="col">Relevance</th>
                <th scope="col">Snippet</th>
              </tr>
            </thead>
            <tbody>
              {results.map((item) => {
                const pct = Math.min(100, Math.max(6, Math.round((item.score / maxScore) * 100)));
                return (
                  <tr key={`${item.chunk_id}-${item.source_id}`}>
                    <td>
                      <div className="search-source-cell">
                        <MaterialIcon name={sourceGlyph(item.source_type)} className="search-source-icon" />
                        <div>
                          <strong>{item.heading || item.file_name}</strong>
                          <span className="search-source-file">{item.file_name}</span>
                        </div>
                        {item.freshness ? (
                          <span className={`badge ${item.freshness.status === "fresh" ? "is-good" : item.freshness.status === "stale" ? "is-danger" : "is-warning"}`}>
                            {item.freshness.status}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>{item.source_type}</td>
                    <td>{item.locator || "—"}</td>
                    <td>
                      <div
                        className="search-relevance"
                        title={`Retrieval score (${modeLabel} mode): ${item.score.toFixed(3)}. The bar is relative to the top result in this set.`}
                      >
                        <span className="search-relevance-bar">
                          <span style={{ width: `${pct}%` }} />
                        </span>
                        <span className="search-relevance-value">{item.score.toFixed(3)}</span>
                      </div>
                    </td>
                    <td>
                      <span className="search-snippet">{item.snippet}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {!loading && hasSearched && results.length === 0 ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-card">
            <MaterialIcon name="travel_explore" className="workspace-empty-icon" />
            <h2>No matching evidence found.</h2>
            <p>The system finished retrieval but found no indexed match for this query in the sources visible to your account. If a file was uploaded recently, it may still be indexing or outside your current visibility scope.</p>
            <div className="workspace-empty-actions">
              <Link href="/console/workspace/sources" className="stitch-button stitch-button-secondary stitch-button-small">Check My Sources</Link>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
