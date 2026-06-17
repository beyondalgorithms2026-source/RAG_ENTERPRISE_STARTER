"use client";

import { MaterialIcon } from "@/components/icons";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Select } from "@/components/ui/Select";
import { TextInput } from "@/components/ui/TextInput";
import { Toggle } from "@/components/ui/Toggle";
import { browserFetch } from "@/lib/api-browser";
import type { SearchResponse, SearchResult } from "@/lib/types";

const MODE_LABELS: Record<string, string> = {
  hybrid: "Hybrid",
  vector: "Semantic",
  keyword: "Keyword",
};

const DATE_WINDOWS: Record<string, number> = {
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
};

const UNASSIGNED_CORPUS = "Unassigned";

function sourceGlyph(sourceType: string) {
  const value = sourceType.toLowerCase();
  if (value.includes("pdf")) return "picture_as_pdf";
  if (value.includes("doc") || value.includes("text") || value.includes("md")) return "description";
  return "link";
}

function corpusOf(item: SearchResult) {
  return item.corpus_name?.trim() || UNASSIGNED_CORPUS;
}

function indexedAtMs(item: SearchResult): number | null {
  const f = item.freshness;
  const ts = f?.last_ingested_at || f?.observed_at || f?.last_synced_at;
  if (!ts) return null;
  const parsed = Date.parse(ts);
  return Number.isNaN(parsed) ? null : parsed;
}

const FRESHNESS_ORDER: Record<string, number> = { fresh: 0, unknown: 1, stale: 2 };

export function SearchWorkspace() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [facetSourceTypes, setFacetSourceTypes] = useState<Set<string>>(new Set());
  const [facetCorpora, setFacetCorpora] = useState<Set<string>>(new Set());
  const [facetFreshness, setFacetFreshness] = useState<Set<string>>(new Set());
  const [indexedWithin, setIndexedWithin] = useState("all");
  const [sortBy, setSortBy] = useState("relevance");

  const hasSearched = result !== null;
  const allResults = useMemo(() => result?.results ?? [], [result]);
  const modeLabel = MODE_LABELS[result?.mode ?? mode] ?? (result?.mode ?? mode);

  const sourceTypeOptions = useMemo(
    () => Array.from(new Set(allResults.map((item) => item.source_type).filter(Boolean))).sort(),
    [allResults],
  );
  const corpusOptions = useMemo(
    () => Array.from(new Set(allResults.map(corpusOf))).sort(),
    [allResults],
  );
  const freshnessOptions = useMemo(
    () => Array.from(new Set(allResults.map((item) => item.freshness?.status).filter(Boolean) as string[])).sort(),
    [allResults],
  );

  const visibleResults = useMemo(() => {
    const now = Date.now();
    const windowMs = DATE_WINDOWS[indexedWithin];
    const filtered = allResults.filter((item) => {
      if (facetSourceTypes.size && !facetSourceTypes.has(item.source_type)) return false;
      if (facetCorpora.size && !facetCorpora.has(corpusOf(item))) return false;
      if (facetFreshness.size && !facetFreshness.has(item.freshness?.status ?? "")) return false;
      if (windowMs) {
        const at = indexedAtMs(item);
        if (at === null || now - at > windowMs) return false;
      }
      return true;
    });
    const sorted = [...filtered];
    if (sortBy === "file_asc") {
      sorted.sort((a, b) => a.file_name.localeCompare(b.file_name) || b.score - a.score);
    } else if (sortBy === "source_type") {
      sorted.sort((a, b) => a.source_type.localeCompare(b.source_type) || b.score - a.score);
    } else if (sortBy === "freshness") {
      sorted.sort(
        (a, b) =>
          (FRESHNESS_ORDER[a.freshness?.status ?? "unknown"] ?? 1) -
            (FRESHNESS_ORDER[b.freshness?.status ?? "unknown"] ?? 1) || b.score - a.score,
      );
    } else {
      sorted.sort((a, b) => b.score - a.score);
    }
    return sorted;
  }, [allResults, facetSourceTypes, facetCorpora, facetFreshness, indexedWithin, sortBy]);

  const visibleMaxScore = visibleResults.reduce((max, item) => Math.max(max, item.score), 0) || 1;
  const activeFacetCount =
    facetSourceTypes.size + facetCorpora.size + facetFreshness.size + (indexedWithin !== "all" ? 1 : 0);

  function toggleIn(setter: (updater: (prev: Set<string>) => Set<string>) => void, value: string) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function clearFilters() {
    setFacetSourceTypes(new Set());
    setFacetCorpora(new Set());
    setFacetFreshness(new Set());
    setIndexedWithin("all");
  }

  async function runSearchValue(value: string) {
    if (!value.trim()) {
      return;
    }
    setLoading(true);
    setError("");
    clearFilters();
    try {
      const payload = await browserFetch<SearchResponse>("/search", {
        method: "POST",
        json: { question: value, k: 8, mode, debug: true },
      });
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  function runSearch() {
    void runSearchValue(query);
  }

  // Bridge from Ask: arrive at /search?q=… → prefill and run once.
  const bridgedRef = useRef(false);
  useEffect(() => {
    const incoming = searchParams.get("q");
    if (incoming && !bridgedRef.current) {
      bridgedRef.current = true;
      setQuery(incoming);
      void runSearchValue(incoming);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

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
          {query.trim() ? (
            <Link
              href={`/console/workspace/chat?q=${encodeURIComponent(query.trim())}`}
              className="stitch-button stitch-button-secondary stitch-button-small"
              title="Ask this question and get a grounded answer with citations"
            >
              <MaterialIcon name="forum" />
              Ask in chat
            </Link>
          ) : null}
        </div>
        {error ? <div className="error-banner" role="alert">{error}</div> : null}
        {!loading && hasSearched && allResults.length > 0 ? (
          <div className="search-result-summary">
            <strong>{visibleResults.length}</strong>
            {visibleResults.length === allResults.length ? "" : ` of ${allResults.length}`} result
            {allResults.length === 1 ? "" : "s"} · {modeLabel} retrieval
            {typeof result?.latency_ms === "number" ? <span> · {Math.round(result.latency_ms)}ms</span> : null}
          </div>
        ) : null}
      </section>

      {!loading && hasSearched && allResults.length > 0 ? (
        <section className="search-facets" aria-label="Filter and sort results">
          {sourceTypeOptions.length > 0 ? (
            <div className="search-facet-group">
              <span className="search-facet-label">Source type</span>
              <div className="search-facet-options">
                {sourceTypeOptions.map((value) => (
                  <Toggle
                    key={value}
                    label={value}
                    checked={facetSourceTypes.has(value)}
                    onChange={() => toggleIn(setFacetSourceTypes, value)}
                  />
                ))}
              </div>
            </div>
          ) : null}
          {corpusOptions.length > 1 ? (
            <div className="search-facet-group">
              <span className="search-facet-label">Corpus</span>
              <div className="search-facet-options">
                {corpusOptions.map((value) => (
                  <Toggle
                    key={value}
                    label={value}
                    checked={facetCorpora.has(value)}
                    onChange={() => toggleIn(setFacetCorpora, value)}
                  />
                ))}
              </div>
            </div>
          ) : null}
          {freshnessOptions.length > 1 ? (
            <div className="search-facet-group">
              <span className="search-facet-label">Freshness</span>
              <div className="search-facet-options">
                {freshnessOptions.map((value) => (
                  <Toggle
                    key={value}
                    label={value}
                    checked={facetFreshness.has(value)}
                    onChange={() => toggleIn(setFacetFreshness, value)}
                  />
                ))}
              </div>
            </div>
          ) : null}
          <div className="search-facet-group">
            <span className="search-facet-label">Indexed</span>
            <Select className="search-facet-select" value={indexedWithin} onChange={(event) => setIndexedWithin(event.target.value)} aria-label="Indexed within">
              <option value="all">Any time</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </Select>
          </div>
          <div className="search-facet-group">
            <span className="search-facet-label">Sort by</span>
            <Select className="search-facet-select" value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort results">
              <option value="relevance">Relevance</option>
              <option value="file_asc">File name (A–Z)</option>
              <option value="freshness">Freshness</option>
              <option value="source_type">Source type</option>
            </Select>
          </div>
          {activeFacetCount > 0 ? (
            <button type="button" className="stitch-button stitch-button-secondary stitch-button-small" onClick={clearFilters}>
              Clear filters ({activeFacetCount})
            </button>
          ) : null}
        </section>
      ) : null}

      {loading ? (
        <div className="workspace-empty-state" role="status">
          <div className="workspace-empty-card">
            <MaterialIcon name="progress_activity" className="workspace-empty-icon spin" />
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

      {!loading && allResults.length > 0 && visibleResults.length > 0 ? (
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
              {visibleResults.map((item) => {
                const pct = Math.min(100, Math.max(6, Math.round((item.score / visibleMaxScore) * 100)));
                return (
                  <tr key={`${item.chunk_id}-${item.source_id}`}>
                    <td>
                      <div className="search-source-cell">
                        <MaterialIcon name={sourceGlyph(item.source_type)} className="search-source-icon" />
                        <div>
                          <strong>{item.heading || item.file_name}</strong>
                          <span className="search-source-file">{item.file_name}{item.corpus_name ? ` · ${item.corpus_name}` : ""}</span>
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
                        title={`Retrieval score (${modeLabel} mode): ${item.score.toFixed(3)}. The bar is relative to the top visible result.`}
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

      {!loading && hasSearched && allResults.length > 0 && visibleResults.length === 0 ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-card">
            <MaterialIcon name="travel_explore" className="workspace-empty-icon" />
            <h2>No results match the current filters.</h2>
            <p>{allResults.length} result{allResults.length === 1 ? "" : "s"} were retrieved, but none match the selected facets. Clear the filters to see them.</p>
            <div className="workspace-empty-actions">
              <button type="button" className="stitch-button stitch-button-primary stitch-button-small" onClick={clearFilters}>Clear filters</button>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && hasSearched && allResults.length === 0 ? (
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
