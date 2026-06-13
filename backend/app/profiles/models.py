from typing import Optional

from pydantic import BaseModel


class EmbeddingProfileConfig(BaseModel):
    model: str
    dimension: int
    batch_size: int = 32


class RerankerProfileConfig(BaseModel):
    enabled: bool = False
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_n: Optional[int] = None
    score_threshold: Optional[float] = None
    enabled_modes: list[str] = []
    enabled_corpora: list[str] = []
    min_candidate_count: int = 0
    max_candidate_count: Optional[int] = None
    latency_budget_ms: Optional[int] = None
    mmr_enabled: bool = False
    mmr_lambda: float = 0.5


class LLMProfileConfig(BaseModel):
    provider: str = "ollama"
    model: str = "gpt-oss:20b-cloud"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    timeout_s: int = 60
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: Optional[int] = None
    structured_output_mode: str = "native_json"
    reasoning_effort: Optional[str] = None


class RetrievalProfileConfig(BaseModel):
    default_mode: str = "hybrid"
    top_k_initial: int = 30
    hybrid_alpha: float = 0.65
    vector_candidates: int = 30
    keyword_candidates: int = 30
    deep_research_alpha: float = 0.2
    deep_research_vector_candidates: int = 24
    deep_research_keyword_candidates: int = 36
    fusion_method: str = "linear"
    rrf_k: int = 60
    query_transform_enabled: bool = False
    rewrite_enabled: bool = False
    expansion_enabled: bool = False
    hyde_enabled: bool = False
    transform_timeout_ms: int = 750
    transform_max_variants: int = 3
    multi_query_enabled: bool = False
    semantic_cache_enabled: bool = False
    semantic_cache_ttl_seconds: int = 900
    # AR6: semantic-cache similarity matching is governed per-policy
    # (semantic_cache_policy_versions.similarity_threshold + match_mode), not on
    # the retrieval profile. The former dead field here was removed.


class EvalPackConfig(BaseModel):
    dataset_name: str
    cases_path: str
    description: str = ""


PROFILE_TYPE_MODELS: dict[str, type[BaseModel]] = {
    "embedding": EmbeddingProfileConfig,
    "reranker": RerankerProfileConfig,
    "llm": LLMProfileConfig,
    "retrieval": RetrievalProfileConfig,
    "eval_pack": EvalPackConfig,
}
