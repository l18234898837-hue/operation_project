from app.core.config import Settings


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
