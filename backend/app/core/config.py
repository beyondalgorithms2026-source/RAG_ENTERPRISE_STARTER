import os

from pydantic_settings import BaseSettings


CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CORE_DIR)
BACKEND_DIR = os.path.dirname(APP_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
ENV_FILE_PATH = os.path.join(BACKEND_DIR, ".env")


class Settings(BaseSettings):
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

    # Retrieval configuration
    RETRIEVAL_MODE: str = "hybrid"
    RERANK_ENABLED: bool = False
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    TOP_K_INITIAL: int = 30
    HYBRID_ALPHA: float = 0.65
    VECTOR_CANDIDATES: int = 30
    KEYWORD_CANDIDATES: int = 30

    # Enrichment flags
    ENABLE_GRAPH: bool = False
    ENABLE_TEMPORAL: bool = False
    ENABLE_ONTOLOGY: bool = False
    EXTRACT_ENTITIES: bool = False
    EXTRACT_RELATIONS: bool = False
    EXTRACT_TEMPORAL_METADATA: bool = False
    BUILD_GRAPH_ON_INGEST: bool = False

    # Query-time orchestration and routing
    ALLOW_LAZY_ENRICHMENT: bool = True
    TEMPORAL_RERANK_ENABLED: bool = False
    USE_QUERY_ROUTER: bool = True

    # Builder/debug flags
    ENABLE_COMPARISON_VIEW: bool = True
    ENABLE_RETRIEVAL_TRACE: bool = True
    ENABLE_GRAPH_EXPLAINABILITY: bool = True

    class Config:
        env_file = ENV_FILE_PATH
        env_file_encoding = "utf-8"


settings = Settings()
