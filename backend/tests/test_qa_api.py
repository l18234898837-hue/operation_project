import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.qa import QaAskRequest, QaAskResponse, QaReferenceSchema


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
    response = QaAskResponse(
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
    assert response.decision["used_knowledge_base"] is False


@pytest.mark.parametrize("answer_type", ["rag", "general_llm", "refused", "none"])
def test_qa_response_supports_answer_types(answer_type):
    response = QaAskResponse(
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
    )

    assert reference.rerank_score == 0.9


def test_qa_ask_endpoint_returns_response_with_references():
    app = create_app()

    async def fake_answer_question_dependency(request):
        return QaAskResponse(
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
