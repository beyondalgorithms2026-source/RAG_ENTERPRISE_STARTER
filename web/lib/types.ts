export type SearchResult = {
  chunk_id: number;
  source_id: number;
  source_part_id?: number | null;
  file_name: string;
  source_type: string;
  heading: string;
  locator?: string | null;
  snippet: string;
  score: number;
  rerank_score?: number | null;
  vector_score?: number | null;
  keyword_score?: number | null;
  combined_score?: number | null;
  rank_score?: number | null;
};

export type SearchResponse = {
  results: SearchResult[];
  latency_ms: number;
  mode: string;
  debug_info?: Record<string, unknown>;
};

export type Citation = {
  citation_id: string;
  source_id: number;
  source_part_id?: number | null;
  chunk_id: number;
  file_name: string;
  source_type: string;
  heading: string;
  locator?: string | null;
  snippet: string;
};

export type AskResponse = {
  answer?: string | null;
  citations: Citation[];
  used_chunks_count: number;
  latency_ms: number;
  debug_info?: Record<string, unknown> | null;
  mode?: string | null;
  cache_info?: {
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
