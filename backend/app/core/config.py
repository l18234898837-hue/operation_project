from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

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

    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
