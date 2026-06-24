from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ORDERED_SECTIONS = [
    ("应用基础配置", ["APP_ENV", "APP_PORT", "APP_NAME", "MODEL_API_TIMEOUT_SECONDS"]),
    ("PostgreSQL 本地数据库配置", ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]),
    ("Redis 预留配置", ["REDIS_HOST", "REDIS_PORT", "REDIS_DB"]),
    ("SiliconFlow Chat 模型配置", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]),
    ("SiliconFlow Embedding 模型配置", ["EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIMENSION"]),
    ("SiliconFlow Rerank 模型配置", ["RERANK_BASE_URL", "RERANK_API_KEY", "RERANK_MODEL", "RERANK_ENABLED", "RERANK_TOP_N"]),
    ("检索参数", ["RETRIEVAL_VECTOR_TOP_K", "RETRIEVAL_KEYWORD_TOP_K", "RETRIEVAL_RRF_TOP_K", "RETRIEVAL_FINAL_TOP_K", "RETRIEVAL_RRF_K"]),
    ("QA 阈值配置", ["QA_RERANK_MIN_SCORE", "QA_RERANK_STRONG_SCORE", "QA_MAX_QUESTION_CHARS", "QA_REFERENCE_TOP_K", "QA_INTENT_MODEL", "QA_CHAT_MODEL"]),
    ("多轮会话配置", ["CONVERSATION_HISTORY_TURNS", "CONVERSATION_SUMMARY_AFTER_TURNS", "CONVERSATION_SUMMARY_REFRESH_TURNS", "CONVERSATION_CONTEXT_MAX_CHARS", "CONVERSATION_ANSWER_EXCERPT_CHARS"]),
]

DEFAULTS = {
    "APP_ENV": "dev",
    "APP_PORT": "8000",
    "APP_NAME": "PV QA Assistant",
    "MODEL_API_TIMEOUT_SECONDS": "180",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_NAME": "operation_pv",
    "DB_USER": "postgres",
    "DB_PASSWORD": "your_password",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "LLM_BASE_URL": "https://api.siliconflow.cn/v1",
    "LLM_API_KEY": "your_api_key",
    "LLM_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "EMBEDDING_BASE_URL": "https://api.siliconflow.cn/v1",
    "EMBEDDING_API_KEY": "your_api_key",
    "EMBEDDING_MODEL": "BAAI/bge-m3",
    "EMBEDDING_DIMENSION": "1024",
    "RERANK_BASE_URL": "https://api.siliconflow.cn/v1",
    "RERANK_API_KEY": "your_api_key",
    "RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
    "RERANK_ENABLED": "true",
    "RERANK_TOP_N": "5",
    "RETRIEVAL_VECTOR_TOP_K": "20",
    "RETRIEVAL_KEYWORD_TOP_K": "20",
    "RETRIEVAL_RRF_TOP_K": "20",
    "RETRIEVAL_FINAL_TOP_K": "5",
    "RETRIEVAL_RRF_K": "60",
    "QA_RERANK_MIN_SCORE": "0.2",
    "QA_RERANK_STRONG_SCORE": "0.6",
    "QA_MAX_QUESTION_CHARS": "500",
    "QA_REFERENCE_TOP_K": "5",
    "QA_INTENT_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "QA_CHAT_MODEL": "deepseek-ai/DeepSeek-V4-Flash",
    "CONVERSATION_HISTORY_TURNS": "10",
    "CONVERSATION_SUMMARY_AFTER_TURNS": "10",
    "CONVERSATION_SUMMARY_REFRESH_TURNS": "5",
    "CONVERSATION_CONTEXT_MAX_CHARS": "8000",
    "CONVERSATION_ANSWER_EXCERPT_CHARS": "500",
}


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def render_env(values: dict[str, str]) -> str:
    parts: list[str] = []
    used: set[str] = set()
    for title, keys in ORDERED_SECTIONS:
        parts.append(f"# {title}")
        for key in keys:
            value = values.get(key, DEFAULTS.get(key, ""))
            parts.append(f"{key}={value}")
            used.add(key)
        parts.append("")

    extras = sorted(key for key in values if key not in used)
    if extras:
        parts.append("# 其他自定义配置")
        for key in extras:
            parts.append(f"{key}={values[key]}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def normalize_file(path: Path) -> None:
    values = {**DEFAULTS, **parse_env(path)}
    path.write_text(render_env(values), encoding="utf-8")


def main() -> None:
    normalize_file(PROJECT_ROOT / ".env.example")
    print("normalized .env.example")
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        normalize_file(env_path)
        print("normalized .env without printing secret values")


if __name__ == "__main__":
    main()
