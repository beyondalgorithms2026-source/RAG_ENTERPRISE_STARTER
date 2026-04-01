import os

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
BACKEND_DIR = os.path.dirname(APP_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
ENV_FILE_PATH = os.path.join(BACKEND_DIR, ".env")


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields from .env file
    )

    # Project-isolated fallback used when backend/.env is absent.
    DATABASE_URL: str = "postgresql://rag_enterprise_starter:rag_enterprise_starter_dev_pass@localhost:55432/rag_enterprise_starter"
    UPLOAD_DIR: str = os.path.join(REPO_ROOT, "data", "uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = ("pdf", "docx", "pptx", "xlsx", "eml", "txt", "md")

    # Embedding configuration
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_BATCH_SIZE: int = 32

    # LLM configuration
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "deepseek-v3.1:671b-cloud"
    LLM_TIMEOUT_S: int = 60
    LLM_API_KEY: str = ""
    OLLAMA_API_KEY: str = ""

    # Auth / OIDC configuration
    AUTH_ENABLED: bool = False
    AUTH_COOKIE_NAME: str = "rag_access_token"
    AUTH_STATE_COOKIE_NAME: str = "rag_oidc_state"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_STATE_SIGNING_SECRET: str = "rag-enterprise-starter-dev-state-secret"
    OIDC_DISCOVERY_URL: str = ""
    OIDC_ISSUER: str = ""
    OIDC_AUDIENCE: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/callback"
    OIDC_SCOPES: str = "openid profile email"
    OIDC_ROLE_CLAIM: str = "roles"
    OIDC_GROUPS_CLAIM: str = "groups"
    OIDC_ADMIN_ROLES: str = "admin"
    OIDC_APPROVER_ROLES: str = "approver"
    OIDC_ALLOWED_ALGORITHMS: str = "RS256"

    # Retrieval configuration
    RETRIEVAL_MODE: str = "hybrid"
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    TOP_K_INITIAL: int = 30
    HYBRID_ALPHA: float = 0.65
    VECTOR_CANDIDATES: int = 30
    KEYWORD_CANDIDATES: int = 30

    # Enrichment flags
    #
    # These are enabled by default so `graph_hybrid` and `full` can use the
    # richer retrieval stack when the user explicitly selects those modes.
    #
    # If you need to reduce ingestion cost, latency, token usage, or overall
    # infrastructure spend, this is the main area to turn back to False.
    # Important: changing these flags only affects newly processed or
    # re-enriched sources. Existing sources need re-ingestion or re-enrichment
    # before graph/temporal/ontology artifacts become available.
    ENABLE_GRAPH: bool = True
    ENABLE_TEMPORAL: bool = True
    ENABLE_ONTOLOGY: bool = True
    EXTRACT_ENTITIES: bool = True
    EXTRACT_RELATIONS: bool = True
    EXTRACT_TEMPORAL_METADATA: bool = True
    BUILD_GRAPH_ON_INGEST: bool = True

    # Query-time orchestration and routing
    ALLOW_LAZY_ENRICHMENT: bool = True
    TEMPORAL_RERANK_ENABLED: bool = False
    USE_QUERY_ROUTER: bool = True

    # Builder/debug flags
    ENABLE_COMPARISON_VIEW: bool = True
    ENABLE_RETRIEVAL_TRACE: bool = True
    ENABLE_GRAPH_EXPLAINABILITY: bool = True


settings = Settings()
