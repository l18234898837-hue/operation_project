from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.models.rag import QaTraceStep


@dataclass(frozen=True)
class QaTraceStepData:
    step_name: str
    duration_ms: int
    status: str = "success"
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class QaTraceCollector:
    trace_id: str
    steps: list[QaTraceStepData] = field(default_factory=list)

    def record_step(
        self,
        step_name: str,
        duration_ms: int,
        status: str = "success",
        model_name: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append(
            QaTraceStepData(
                step_name=step_name,
                duration_ms=duration_ms,
                status=status,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_message=error_message,
                metadata=metadata,
            )
        )

    def timings_ms(self) -> dict[str, int]:
        return {f"{step.step_name}_ms": step.duration_ms for step in self.steps}


def persist_trace_steps(
    session: Session,
    record_id: uuid.UUID,
    collector: QaTraceCollector,
) -> None:
    for step in collector.steps:
        session.add(
            QaTraceStep(
                qa_record_id=record_id,
                trace_id=collector.trace_id,
                step_name=step.step_name,
                duration_ms=step.duration_ms,
                status=step.status,
                model_name=step.model_name,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                error_message=step.error_message,
                step_metadata=step.metadata,
            )
        )
