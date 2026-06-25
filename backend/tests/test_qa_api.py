import pytest
import uuid
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.qa import QaAskRequest, QaAskResponse, QaReferenceSchema
from app.services.qa_service import _add_references, _reference_schema


def test_qa_request_trims_question():
    request = QaAskRequest(question="  逆变器漏电流报警怎么处理？  ")

    assert request.question == "逆变器漏电流报警怎么处理？"


def test_qa_request_rejects_empty_question_after_trim():
    with pytest.raises(ValidationError):
        QaAskRequest(question="   ")


def test_qa_request_rejects_invalid_session_id():
    with pytest.raises(ValidationError):
        QaAskRequest(question="逆变器绝缘阻抗低怎么排查？", session_id="not-a-uuid")


def test_qa_response_allows_empty_references_for_general_llm():
    session_id = uuid.uuid4()
    response = QaAskResponse(
        session_id=session_id,
        trace_id="trace-1",
        answer_type="general_llm",
        intent="general_explanation",
        answer="无功功率是交流系统中用于建立电磁场的功率。",
        confidence=0.82,
        references=[],
        decision={
            "route": "general_llm",
            "used_knowledge_base": False,
            "refusal_reason": None,
        },
    )

    assert response.references == []
    assert response.session_id == session_id
    assert response.decision["used_knowledge_base"] is False


@pytest.mark.parametrize("answer_type", ["rag", "general_llm", "refused", "none"])
def test_qa_response_supports_answer_types(answer_type):
    response = QaAskResponse(
        session_id=uuid.uuid4(),
        trace_id="trace-1",
        answer_type=answer_type,
        intent="knowledge_base_qa",
        answer="测试回答",
        confidence=None,
        references=[],
        decision={},
    )

    assert response.answer_type == answer_type


@pytest.mark.parametrize(
    "intent",
    [
        "knowledge_base_qa",
        "general_explanation",
        "out_of_scope",
        "realtime_external",
        "invalid_input",
    ],
)
def test_qa_response_supports_intents(intent):
    response = QaAskResponse(
        session_id=uuid.uuid4(),
        trace_id="trace-1",
        answer_type="none",
        intent=intent,
        answer="测试回答",
        confidence=None,
        references=[],
        decision={},
    )

    assert response.intent == intent


def test_qa_reference_schema_contains_scores():
    reference = QaReferenceSchema(
        rank=1,
        segment_id="segment-1",
        document_id="document-1",
        heading_path="逆变器故障与维护 > 漏电流故障",
        excerpt="漏电流可能与组件绝缘层破损有关。",
        vector_score=0.6,
        keyword_score=0.4,
        rrf_score=0.03,
        rerank_score=0.9,
        visible=True,
    )

    assert reference.rerank_score == 0.9
    assert reference.visible is True


def test_qa_reference_schema_contains_document_file_name():
    reference = QaReferenceSchema(
        rank=1,
        segment_id="segment-1",
        document_id="document-1",
        document_file_name="inverter-maintenance.md",
        heading_path="逆变器故障与维护 > 漏电流故障",
        excerpt="漏电流可能与组件绝缘层破损有关。",
        vector_score=0.6,
        keyword_score=0.4,
        rrf_score=0.03,
        rerank_score=0.9,
        visible=True,
    )

    assert reference.document_file_name == "inverter-maintenance.md"
    assert reference.model_dump()["document_file_name"] == "inverter-maintenance.md"


class _ReferenceItem:
    segment_id = "segment-1"
    document_id = "document-1"
    heading_path = "逆变器故障与维护 > 漏电流故障"
    clean_text = "漏电流可能与组件绝缘层破损有关。"
    vector_score = 0.6
    keyword_score = 0.4
    rrf_score = 0.03
    rerank_score = 0.9


def test_reference_schema_uses_document_file_name():
    schema = _reference_schema(
        rank=1,
        item=_ReferenceItem(),
        visible=True,
        document_file_name="inverter-maintenance.md",
    )

    assert schema.document_file_name == "inverter-maintenance.md"


class _ExecuteRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ReferenceSession:
    def __init__(self, rows):
        self.rows = rows
        self.added = []
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return _ExecuteRows(self.rows)

    def add(self, item):
        self.added.append(item)


def test_add_references_maps_document_file_name_for_parseable_uuid_strings():
    document_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    segment_id = uuid.UUID("87654321-4321-8765-4321-876543218765")
    item = _ReferenceItem()
    item.document_id = f"{{{str(document_id).upper()}}}"
    item.segment_id = str(segment_id)
    session = _ReferenceSession([(document_id, "inverter-maintenance.md", None)])
    record = type("Record", (), {"id": uuid.uuid4()})()

    references = _add_references(session, record, [item], visible_top_k=1)

    assert references[0].document_file_name == "inverter-maintenance.md"


def test_add_references_uses_metadata_source_file_name_for_existing_documents():
    document_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    segment_id = uuid.UUID("87654321-4321-8765-4321-876543218765")
    item = _ReferenceItem()
    item.document_id = str(document_id)
    item.segment_id = str(segment_id)
    session = _ReferenceSession([(document_id, None, {"source_file_name": "legacy-maintenance.md"})])
    record = type("Record", (), {"id": uuid.uuid4()})()

    references = _add_references(session, record, [item], visible_top_k=1)

    assert references[0].document_file_name == "legacy-maintenance.md"


def test_add_references_does_not_fallback_to_document_title_without_file_name():
    document_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    segment_id = uuid.UUID("87654321-4321-8765-4321-876543218765")
    item = _ReferenceItem()
    item.document_id = str(document_id)
    item.segment_id = str(segment_id)
    session = _ReferenceSession([(document_id, None, {})])
    record = type("Record", (), {"id": uuid.uuid4()})()

    references = _add_references(session, record, [item], visible_top_k=1)

    assert references[0].document_file_name is None
    assert "title" not in str(session.statement)


def test_qa_ask_endpoint_returns_response_with_references():
    app = create_app()

    async def fake_answer_question_dependency(request):
        return QaAskResponse(
            session_id=uuid.uuid4(),
            trace_id="trace-1",
            answer_type="rag",
            intent="knowledge_base_qa",
            answer="请检查直流线缆和组串绝缘。",
            confidence=0.86,
            references=[
                QaReferenceSchema(
                    rank=1,
                    segment_id="segment-1",
                    document_id="document-1",
                    heading_path="03_线缆接头与绝缘故障 > 4. 绝缘阻抗问题",
                    excerpt="绝缘阻抗问题可以理解为直流线破皮并接地。",
                    vector_score=0.64,
                    keyword_score=0.5,
                    rrf_score=0.03,
                    rerank_score=0.86,
                )
            ],
            decision={
                "route": "rag",
                "used_knowledge_base": True,
                "refusal_reason": None,
            },
        )

    from app.api.qa import get_qa_answerer

    app.dependency_overrides[get_qa_answerer] = lambda: fake_answer_question_dependency
    client = TestClient(app)

    response = client.post(
        "/api/qa/ask",
        json={"question": "逆变器绝缘阻抗低怎么排查？"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer_type"] == "rag"
    assert data["session_id"]
    assert data["references"][0]["heading_path"].startswith("03_线缆接头")


def test_qa_ask_endpoint_rejects_invalid_session_id_before_answerer():
    app = create_app()

    async def fake_answer_question_dependency(request):
        raise AssertionError("answerer should not be called for invalid request")

    from app.api.qa import get_qa_answerer

    app.dependency_overrides[get_qa_answerer] = lambda: fake_answer_question_dependency
    client = TestClient(app)

    response = client.post(
        "/api/qa/ask",
        json={
            "question": "逆变器绝缘阻抗低怎么排查？",
            "session_id": "not-a-uuid",
        },
    )

    assert response.status_code == 422


def test_ask_question_script_imports_safely_without_executing_main():
    import backend.scripts.ask_question as ask_script

    assert hasattr(ask_script, "main")


def test_smoke_qa_script_imports_safely_without_executing_main():
    import backend.scripts.smoke_qa as smoke_script

    assert hasattr(smoke_script, "main")


def test_smoke_multiturn_qa_script_imports_safely_without_executing_main():
    import backend.scripts.smoke_multiturn_qa as smoke_script

    assert hasattr(smoke_script, "main")


def test_chat_qa_script_imports_safely_without_executing_main():
    import backend.scripts.chat_qa as chat_script

    assert hasattr(chat_script, "main")


def test_stream_chat_qa_script_imports_safely_without_executing_main():
    import backend.scripts.stream_chat_qa as stream_script

    assert hasattr(stream_script, "main")


def test_qa_stream_endpoint_returns_event_stream():
    app = create_app()

    async def fake_streamer(request):
        yield 'event: status\ndata: {"stage":"retrieving"}\n\n'
        yield 'event: done\ndata: {"answer_type":"rag"}\n\n'

    from app.api.qa import get_qa_streamer

    app.dependency_overrides[get_qa_streamer] = lambda: fake_streamer
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/qa/ask/stream",
        json={"question": "逆变器绝缘阻抗低怎么排查？"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in body
    assert "event: done" in body
