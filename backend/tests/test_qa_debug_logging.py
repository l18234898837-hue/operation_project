import json
import logging
from types import SimpleNamespace

from app.services.qa_debug_logging import log_qa_debug_event


def test_log_qa_debug_event_does_nothing_when_disabled(caplog):
    logger = logging.getLogger("test.qa_debug.disabled")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_qa_debug_event(
            logger=logger,
            enabled=False,
            event="qa.request.start",
            trace_id="trace-1",
            question="逆变器绝缘阻抗低怎么排查？",
        )

    assert caplog.records == []


def test_log_qa_debug_event_outputs_structured_json_with_preview(caplog):
    logger = logging.getLogger("test.qa_debug.enabled")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_qa_debug_event(
            logger=logger,
            enabled=True,
            event="qa.request.start",
            preview_chars=6,
            trace_id="trace-1",
            question="逆变器绝缘阻抗低怎么排查？",
            session_id="session-1",
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith("qa_debug ")
    payload = json.loads(caplog.records[0].message.removeprefix("qa_debug "))

    assert payload["event"] == "qa.request.start"
    assert payload["trace_id"] == "trace-1"
    assert payload["session_id"] == "session-1"
    assert payload["question_preview"] == "逆变器绝缘阻..."
    assert "question" not in payload


def test_log_qa_debug_event_outputs_full_answer_for_copying(caplog):
    logger = logging.getLogger("test.qa_debug.answer")
    answer = "第一行回答\n第二行回答，包含完整处理建议。"

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_qa_debug_event(
            logger=logger,
            enabled=True,
            event="qa.request.finish",
            preview_chars=4,
            answer=answer,
        )

    payload = json.loads(caplog.records[0].message.removeprefix("qa_debug "))

    assert payload["answer"] == answer
    assert "answer_preview" not in payload


def test_log_qa_debug_event_compacts_evidence_preview(caplog):
    logger = logging.getLogger("test.qa_debug.evidence_preview")
    evidence = [
        SimpleNamespace(
            segment_id="segment-1",
            document_id="document-1",
            heading_path="01 inverter faults > 3.2 grid overvoltage",
            indexed_text="indexed text should not be logged",
            clean_text="clean text should not be logged",
            vector_score=0.7,
            keyword_score=0.4,
            rrf_score=0.03,
            rerank_score=0.8,
        )
    ]

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_qa_debug_event(
            logger=logger,
            enabled=True,
            event="qa.evidence.retrieved",
            evidence_preview_enabled=True,
            evidence=evidence,
        )

    payload = json.loads(caplog.records[0].message.removeprefix("qa_debug "))

    assert payload["evidence_count"] == 1
    assert payload["evidence_preview"] == [
        {
            "segment_id": "segment-1",
            "document_id": "document-1",
            "heading_path": "01 inverter faults > 3.2 grid overvoltage",
            "rerank_score": 0.8,
            "vector_score": 0.7,
            "keyword_score": 0.4,
            "rrf_score": 0.03,
            "clean_text_length": 31,
            "indexed_text_length": 33,
        }
    ]
    assert "clean text should not be logged" not in caplog.records[0].message
    assert "indexed text should not be logged" not in caplog.records[0].message
