from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.answer_generation import generate_general_answer, generate_rag_answer
from app.services.qa_service import QaDependencies
from app.services.query_understanding import QueryUnderstandingResult, understand_query
from app.services.retrieval import retrieve_evidence
from app.services.siliconflow import (
    SiliconFlowChatClient,
    SiliconFlowEmbeddingClient,
    SiliconFlowRerankClient,
)


class RealUnderstandingClient:
    def __init__(
        self,
        chat_client: SiliconFlowChatClient,
        max_question_chars: int,
    ) -> None:
        self._chat_client = chat_client
        self._max_question_chars = max_question_chars

    async def understand(self, question: str) -> QueryUnderstandingResult:
        return await understand_query(
            question=question,
            chat_client=self._chat_client,
            max_question_chars=self._max_question_chars,
        )


class RealRetriever:
    def __init__(
        self,
        session: Session,
        embedding_client: SiliconFlowEmbeddingClient,
        rerank_client: SiliconFlowRerankClient | None,
    ) -> None:
        self._session = session
        self._embedding_client = embedding_client
        self._rerank_client = rerank_client

    async def retrieve(self, query: str) -> list[object]:
        return await retrieve_evidence(
            session=self._session,
            query=query,
            embedding_client=self._embedding_client,
            rerank_client=self._rerank_client,
            vector_top_k=settings.retrieval_vector_top_k,
            keyword_top_k=settings.retrieval_keyword_top_k,
            rrf_top_k=settings.retrieval_rrf_top_k,
            final_top_k=settings.retrieval_final_top_k,
            rrf_k=settings.retrieval_rrf_k,
        )


class RealAnswerClient:
    def __init__(self, chat_client: SiliconFlowChatClient) -> None:
        self._chat_client = chat_client

    async def generate_rag(
        self,
        question: str,
        evidence: list[object],
        cautious: bool,
    ) -> str:
        return await generate_rag_answer(
            chat_client=self._chat_client,
            question=question,
            evidence=evidence,
            cautious=cautious,
        )

    async def generate_general(self, question: str) -> str:
        return await generate_general_answer(
            chat_client=self._chat_client,
            question=question,
        )


def build_qa_dependencies(
    session: Session,
    intent_chat_client: SiliconFlowChatClient,
    answer_chat_client: SiliconFlowChatClient,
    embedding_client: SiliconFlowEmbeddingClient,
    rerank_client: SiliconFlowRerankClient | None,
) -> QaDependencies:
    return QaDependencies(
        understanding_client=RealUnderstandingClient(
            chat_client=intent_chat_client,
            max_question_chars=settings.qa_max_question_chars,
        ),
        retriever=RealRetriever(
            session=session,
            embedding_client=embedding_client,
            rerank_client=rerank_client,
        ),
        answer_client=RealAnswerClient(answer_chat_client),
    )
