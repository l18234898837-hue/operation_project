import app.models
import app.models.rag  # noqa: F401

from app.db.base import Base
from sqlalchemy.orm import configure_mappers


def test_base_metadata_is_available():
    assert app.models.Base is Base
    assert Base.metadata is not None


def test_rag_tables_are_registered():
    expected = {
        "kb_document",
        "parse_task",
        "kb_document_segment",
        "faq_item",
        "qa_session",
        "qa_record",
        "qa_reference",
        "qa_unanswered",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_segment_embedding_dimension_is_1024():
    segment = Base.metadata.tables["kb_document_segment"]
    assert segment.c.embedding.type.dim == 1024


def test_rag_mappers_configure():
    import app.models.rag  # noqa: F401

    configure_mappers()


def test_rag_spec_critical_columns_are_registered():
    expected_columns = {
        "kb_document": {
            "source_path",
            "file_sha256",
            "file_type",
            "enabled",
            "error_message",
        },
        "parse_task": {"retry_count", "duration_ms"},
        "kb_document_segment": {
            "chunk_index",
            "token_count",
            "char_count",
            "heading_path",
            "section_title",
            "raw_text",
            "clean_text",
            "indexed_text",
            "keyword_text",
            "embedding_model",
            "embedding",
            "segment_metadata",
        },
        "faq_item": {"normalized_question", "enabled", "source_document_id"},
        "qa_record": {
            "trace_id",
            "normalized_question",
            "confidence",
            "model_name",
            "decision_metadata",
        },
        "qa_reference": {"qa_record_id", "rank", "ref_metadata"},
        "qa_unanswered": {"normalized_question", "reason", "resolved_note"},
    }

    for table_name, columns in expected_columns.items():
        table = Base.metadata.tables[table_name]
        assert columns.issubset(set(table.c.keys()))


def test_rag_legacy_column_names_are_not_registered():
    legacy_columns = {
        "kb_document": {"source_uri", "checksum", "mime_type"},
        "kb_document_segment": {"ordinal"},
        "faq_item": {"document_id", "is_enabled"},
        "qa_record": {"confidence_score", "record_metadata"},
        "qa_reference": {"record_id"},
        "qa_unanswered": {"review_note", "resolved_answer"},
    }

    for table_name, columns in legacy_columns.items():
        table = Base.metadata.tables[table_name]
        assert set(table.c.keys()).isdisjoint(columns)


def test_rag_spec_critical_constraints_are_registered():
    document = Base.metadata.tables["kb_document"]
    assert any(
        index.unique and {column.name for column in index.columns} == {"file_sha256"}
        for index in document.indexes
    )

    segment = Base.metadata.tables["kb_document_segment"]
    assert any(
        constraint.name == "uq_kb_document_segment_document_chunk_index"
        for constraint in segment.constraints
    )

    unanswered = Base.metadata.tables["qa_unanswered"]
    assert any(
        constraint.name == "uq_qa_unanswered_record_id"
        for constraint in unanswered.constraints
    )


def test_rag_server_defaults_match_initial_migration():
    expected_defaults = {
        ("kb_document", "status"): "uploaded",
        ("kb_document", "enabled"): "true",
        ("kb_document", "segment_count"): "0",
        ("parse_task", "status"): "pending",
        ("parse_task", "retry_count"): "0",
        ("faq_item", "enabled"): "true",
        ("qa_record", "answer_type"): "none",
        ("qa_unanswered", "status"): "new",
    }

    for (table_name, column_name), expected in expected_defaults.items():
        column = Base.metadata.tables[table_name].c[column_name]
        assert column.server_default is not None
        assert str(column.server_default.arg) == expected
