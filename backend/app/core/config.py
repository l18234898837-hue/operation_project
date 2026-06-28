from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    app_port: int = 8000
    app_name: str = "PV QA Assistant"

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "operation_pv"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_pool_pre_ping: bool = True
    db_connection_prewarm_enabled: bool = True

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    model_api_timeout_seconds: float = 180.0

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_enabled: bool = True
    rerank_top_n: int = 5

    retrieval_vector_top_k: int = 20
    retrieval_keyword_top_k: int = 20
    retrieval_rrf_top_k: int = 20
    retrieval_final_top_k: int = 5
    retrieval_rrf_k: int = 60

    qa_rerank_min_score: float = 0.2
    qa_rerank_strong_score: float = 0.6
    qa_max_question_chars: int = 500
    qa_reference_top_k: int = 5
    qa_intent_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    qa_chat_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    qa_evidence_min_score: float = 0.3
    qa_reference_min_score: float = 0.3
    qa_reference_visible_top_k: int = 3
    qa_reference_max_top_k: int = 5
    qa_debug_log_enabled: bool = False
    qa_debug_question_preview_chars: int = 80
    qa_debug_evidence_preview_enabled: bool = False

    conversation_history_turns: int = 10
    conversation_summary_after_turns: int = 10
    conversation_summary_refresh_turns: int = 5
    conversation_context_max_chars: int = 8000
    conversation_answer_excerpt_chars: int = 500

    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
