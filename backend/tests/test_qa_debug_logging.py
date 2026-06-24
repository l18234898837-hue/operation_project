import json
import logging

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
