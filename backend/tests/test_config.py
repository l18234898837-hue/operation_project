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
