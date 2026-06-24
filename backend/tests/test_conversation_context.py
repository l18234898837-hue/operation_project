from types import SimpleNamespace

from app.models.rag import AnswerType
from app.services.conversation_context import build_conversation_context


def test_build_conversation_context_uses_recent_turns_and_summary():
    records = [
        SimpleNamespace(
            question=f"问题{i}",
            normalized_question=f"规范问题{i}",
            answer=f"回答{i}",
            answer_type=AnswerType.rag,
            references=[
                SimpleNamespace(
                    rank=1,
                    ref_metadata={"heading_path": f"标题路径{i}"},
                )
            ],
        )
        for i in range(12)
    ]

    context = build_conversation_context(
        records=records,
        session_metadata={"conversation_summary": {"summary": "历史摘要"}},
        history_turns=10,
        answer_excerpt_chars=20,
        max_chars=8000,
    )

    assert context.used_history is True
    assert context.session_summary == {"summary": "历史摘要"}
    assert len(context.recent_turns) == 10
    assert context.recent_turns[0]["question"] == "问题2"
    assert context.recent_turns[-1]["top_heading"] == "标题路径11"


def test_build_conversation_context_trims_old_turns_when_context_is_too_large():
    records = [
        SimpleNamespace(
            question=f"问题{i}",
            normalized_question="",
            answer="很长的回答" * 50,
            answer_type=AnswerType.rag,
            references=[],
        )
        for i in range(5)
    ]

    context = build_conversation_context(
        records=records,
        session_metadata=None,
        history_turns=5,
        answer_excerpt_chars=200,
        max_chars=300,
    )

    assert len(context.recent_turns) < 5
