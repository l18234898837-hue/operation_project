import logging

from app.core.config import Settings
from app.main import create_app
from app.services.rag_confidence_policy import (
    LOW_CONFIDENCE_SUPPLEMENT_SCORE,
    STRONG_RAG_SCORE,
)


def test_settings_reads_rag_configuration(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("LLM_MODEL", "test-llm-model")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-embedding-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1536")
    monkeypatch.setenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("RERANK_API_KEY", "test-rerank-key")
    monkeypatch.setenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_TOP_N", "7")
    monkeypatch.setenv("RETRIEVAL_VECTOR_TOP_K", "31")
    monkeypatch.setenv("RETRIEVAL_KEYWORD_TOP_K", "32")
    monkeypatch.setenv("RETRIEVAL_RRF_TOP_K", "33")
    monkeypatch.setenv("RETRIEVAL_FINAL_TOP_K", "8")
    monkeypatch.setenv("RETRIEVAL_RRF_K", "72")

    settings = Settings()

    assert settings.llm_base_url == "https://example.test/v1"
    assert settings.llm_api_key == "test-llm-key"
    assert settings.llm_model == "test-llm-model"
    assert settings.embedding_base_url == "https://api.siliconflow.cn/v1"
    assert settings.embedding_api_key == "test-embedding-key"
    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dimension == 1536
    assert settings.rerank_base_url == "https://api.siliconflow.cn/v1"
    assert settings.rerank_api_key == "test-rerank-key"
    assert settings.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert settings.rerank_enabled is True
    assert settings.rerank_top_n == 7
    assert settings.retrieval_vector_top_k == 31
    assert settings.retrieval_keyword_top_k == 32
    assert settings.retrieval_rrf_top_k == 33
    assert settings.retrieval_final_top_k == 8
    assert settings.retrieval_rrf_k == 72


def test_settings_reads_qa_routing_configuration():
    settings = Settings(
        qa_rerank_min_score="0.2",
        qa_rerank_strong_score="0.6",
        qa_max_question_chars="500",
        qa_reference_top_k="5",
        qa_intent_model="deepseek-ai/DeepSeek-V4-Flash",
        qa_chat_model="deepseek-ai/DeepSeek-V4-Flash",
        model_api_timeout_seconds="240",
    )

    assert settings.qa_rerank_min_score == 0.2
    assert settings.qa_rerank_strong_score == 0.6
    assert settings.qa_max_question_chars == 500
    assert settings.qa_reference_top_k == 5
    assert settings.qa_intent_model == "deepseek-ai/DeepSeek-V4-Flash"
    assert settings.qa_chat_model == "deepseek-ai/DeepSeek-V4-Flash"
    assert settings.model_api_timeout_seconds == 240


def test_settings_uses_rag_confidence_policy_defaults():
    settings = Settings(_env_file=None)

    assert settings.qa_rerank_min_score == LOW_CONFIDENCE_SUPPLEMENT_SCORE
    assert settings.qa_rerank_strong_score == STRONG_RAG_SCORE


def test_settings_reads_multi_turn_conversation_configuration():
    settings = Settings(
        conversation_history_turns="10",
        conversation_summary_after_turns="10",
        conversation_summary_refresh_turns="5",
        conversation_context_max_chars="8000",
        conversation_answer_excerpt_chars="500",
    )

    assert settings.conversation_history_turns == 10
    assert settings.conversation_summary_after_turns == 10
    assert settings.conversation_summary_refresh_turns == 5
    assert settings.conversation_context_max_chars == 8000
    assert settings.conversation_answer_excerpt_chars == 500


def test_settings_reads_reference_filtering_configuration():
    settings = Settings(
        qa_evidence_min_score="0.3",
        qa_reference_min_score="0.3",
        qa_reference_visible_top_k="3",
        qa_reference_max_top_k="5",
    )

    assert settings.qa_evidence_min_score == 0.3
    assert settings.qa_reference_min_score == 0.3
    assert settings.qa_reference_visible_top_k == 3
    assert settings.qa_reference_max_top_k == 5


def test_settings_reads_qa_debug_logging_configuration():
    settings = Settings(
        qa_debug_log_enabled="true",
        qa_debug_question_preview_chars="60",
        qa_debug_evidence_preview_enabled="true",
    )

    assert settings.qa_debug_log_enabled is True
    assert settings.qa_debug_question_preview_chars == 60
    assert settings.qa_debug_evidence_preview_enabled is True


def test_settings_reads_database_pool_configuration():
    settings = Settings(
        db_pool_size="7",
        db_max_overflow="13",
        db_pool_timeout_seconds="9",
        db_pool_recycle_seconds="600",
        db_pool_pre_ping="false",
        db_connection_prewarm_enabled="false",
    )

    assert settings.db_pool_size == 7
    assert settings.db_max_overflow == 13
    assert settings.db_pool_timeout_seconds == 9
    assert settings.db_pool_recycle_seconds == 600
    assert settings.db_pool_pre_ping is False
    assert settings.db_connection_prewarm_enabled is False


def test_create_app_configures_app_logger_for_info_output():
    app_logger = logging.getLogger("app.services.qa_service")
    app_logger.handlers.clear()
    app_logger.setLevel(logging.NOTSET)

    root_logger = logging.getLogger()
    original_root_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)

    try:
        create_app()
        assert app_logger.getEffectiveLevel() == logging.INFO
    finally:
        logging.getLogger("app").handlers.clear()
        root_logger.handlers[:] = original_root_handlers
        root_logger.setLevel(original_root_level)


def test_normalize_env_file_script_imports_safely_without_executing_main():
    import backend.scripts.normalize_env_file as normalize_script

    assert hasattr(normalize_script, "main")


def test_database_url_escapes_special_characters_in_password():
    settings = Settings(
        db_user="postgres",
        db_password="p@ss/word#1",
        db_host="127.0.0.1",
        db_port="5432",
        db_name="operation_pv",
    )

    assert settings.database_url.password == "p@ss/word#1"
    assert (
        settings.database_url.render_as_string(hide_password=False)
        == "postgresql+psycopg://postgres:p%40ss%2Fword%231@127.0.0.1:5432/operation_pv"
    )
