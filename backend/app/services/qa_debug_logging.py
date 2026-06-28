from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any


def log_qa_debug_event(
    logger: logging.Logger,
    enabled: bool,
    event: str,
    preview_chars: int = 80,
    evidence_preview_enabled: bool = False,
    **fields: Any,
) -> None:
    if not enabled:
        return

    payload: dict[str, Any] = {"event": event}
    for key, value in fields.items():
        if value is None:
            continue
        if key == "question":
            payload["question_preview"] = _preview(str(value), preview_chars)
            continue
        if key in {"standalone_question", "normalized_question", "search_query"}:
            payload[key] = _preview(str(value), preview_chars)
            continue
        if key in {"evidence", "references"} and not evidence_preview_enabled:
            payload[f"{key}_count"] = len(value) if isinstance(value, Sequence) else None
            continue
        if key == "evidence" and evidence_preview_enabled:
            payload["evidence_preview"] = _evidence_preview(value)
            payload["evidence_count"] = len(value) if isinstance(value, Sequence) else None
            continue
        payload[key] = _json_safe(value)

    logger.info(
        "qa_debug %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _preview(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _evidence_preview(value: Any) -> list[dict[str, Any]] | Any:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return _json_safe(value)
    return [_evidence_item_preview(item) for item in value]


def _evidence_item_preview(item: Any) -> dict[str, Any]:
    return {
        "segment_id": _json_safe(getattr(item, "segment_id", None)),
        "document_id": _json_safe(getattr(item, "document_id", None)),
        "heading_path": _json_safe(getattr(item, "heading_path", "") or ""),
        "rerank_score": _json_safe(getattr(item, "rerank_score", None)),
        "vector_score": _json_safe(getattr(item, "vector_score", None)),
        "keyword_score": _json_safe(getattr(item, "keyword_score", None)),
        "rrf_score": _json_safe(getattr(item, "rrf_score", None)),
        "clean_text_length": len(getattr(item, "clean_text", "") or ""),
        "indexed_text_length": len(getattr(item, "indexed_text", "") or ""),
    }
