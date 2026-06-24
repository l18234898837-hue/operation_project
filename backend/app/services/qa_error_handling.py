from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class QaExceptionDecision:
    reason: str
    user_message: str
    status_code: int | None
    should_record_unanswered: bool


def classify_qa_exception(exc: Exception) -> QaExceptionDecision:
    if isinstance(exc, httpx.TimeoutException):
        return QaExceptionDecision(
            reason="model_timeout",
            user_message="模型服务请求超时，当前无法可靠生成答案，请稍后重试。",
            status_code=None,
            should_record_unanswered=True,
        )

    if isinstance(exc, httpx.HTTPStatusError):
        return QaExceptionDecision(
            reason="model_http_error",
            user_message="模型服务暂时不可用，当前无法可靠生成答案，请稍后重试。",
            status_code=exc.response.status_code,
            should_record_unanswered=True,
        )

    return QaExceptionDecision(
        reason="qa_internal_error",
        user_message="问答服务处理异常，当前无法可靠生成答案。",
        status_code=None,
        should_record_unanswered=True,
    )
