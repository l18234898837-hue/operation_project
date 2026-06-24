import uuid

from app.models.rag import QaTraceStep
from app.services.qa_trace import QaTraceCollector, persist_trace_steps


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


def test_trace_collector_records_success_step():
    collector = QaTraceCollector(trace_id="trace-1")

    collector.record_step(
        step_name="answer_generation",
        duration_ms=1234,
        status="success",
        model_name="deepseek-ai/DeepSeek-V4-Flash",
        metadata={"route": "rag"},
    )

    assert collector.steps[0].step_name == "answer_generation"
    assert collector.steps[0].duration_ms == 1234
    assert collector.steps[0].metadata == {"route": "rag"}


def test_persist_trace_steps_writes_models():
    session = FakeSession()
    record_id = uuid.uuid4()
    collector = QaTraceCollector(trace_id="trace-1")
    collector.record_step("retrieve_evidence", 900)

    persist_trace_steps(session=session, record_id=record_id, collector=collector)

    assert len(session.added) == 1
    assert isinstance(session.added[0], QaTraceStep)
    assert session.added[0].qa_record_id == record_id
    assert session.added[0].step_name == "retrieve_evidence"
