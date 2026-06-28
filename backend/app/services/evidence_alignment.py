from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# Topic coverage terms for guarding against high rerank scores on the wrong
# fault topic. Keep these policy terms outside qa_service so tuning does not
# require editing the route orchestration code.
TOPIC_TERM_GROUPS: dict[str, tuple[str, ...]] = {
    "communication": (
        "通讯",
        "通信",
        "监控平台",
        "监控",
        "离线",
        "中断",
        "采集器",
        "数据采集器",
        "网关",
        "RS485",
        "4G",
        "网络",
        "后台",
        "平台",
    ),
    "insulation": (
        "绝缘",
        "绝缘阻抗",
        "绝缘电阻",
        "接地",
        "漏电流",
    ),
    "grid_voltage": (
        "电网过压",
        "电网欠压",
        "过压",
        "欠压",
        "电网电压",
        "并网点电压",
    ),
    "temperature": (
        "温度",
        "过温",
        "发热",
        "高温",
        "测温",
        "红外",
        "散热",
        "风扇",
        "风道",
    ),
    "connector": (
        "接头",
        "端子",
        "MC4",
        "插头",
        "插接",
        "压接",
    ),
    "efficiency": (
        "效率",
        "转换效率",
        "线损",
        "损耗",
    ),
    "generation": (
        "发电量",
        "发电少",
        "发电低",
        "不发电",
        "功率低",
        "出力",
    ),
    "shading": (
        "遮挡",
        "阴影",
        "低辐照",
        "辐照",
        "热斑",
        "PID",
    ),
}


@dataclass(frozen=True)
class EvidenceAlignmentResult:
    directly_supported: bool
    reason: str
    question_topics: tuple[str, ...] = ()
    evidence_topics: tuple[str, ...] = ()
    missing_topics: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, object]:
        return {
            "directly_supported": self.directly_supported,
            "reason": self.reason,
            "question_topics": list(self.question_topics),
            "evidence_topics": list(self.evidence_topics),
            "missing_topics": list(self.missing_topics),
        }


def check_evidence_directly_supports_question(
    question: str,
    evidence: list[object],
) -> EvidenceAlignmentResult:
    question_topics = _matched_topics(question)
    if not question_topics:
        return EvidenceAlignmentResult(
            directly_supported=True,
            reason="no_topic_terms_required",
        )

    evidence_text = "\n".join(_evidence_text(item) for item in evidence)
    evidence_topics = _matched_topics(evidence_text)
    missing_topics = tuple(
        topic for topic in question_topics if topic not in evidence_topics
    )
    if missing_topics:
        return EvidenceAlignmentResult(
            directly_supported=False,
            reason="missing_topic_terms",
            question_topics=question_topics,
            evidence_topics=evidence_topics,
            missing_topics=missing_topics,
        )

    return EvidenceAlignmentResult(
        directly_supported=True,
        reason="topic_terms_matched",
        question_topics=question_topics,
        evidence_topics=evidence_topics,
    )


def _matched_topics(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    return tuple(
        topic
        for topic, terms in TOPIC_TERM_GROUPS.items()
        if _contains_any(normalized, terms)
    )


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term.lower() in text for term in terms)


def _evidence_text(item: object) -> str:
    return "\n".join(
        str(getattr(item, field, "") or "")
        for field in ("heading_path", "clean_text")
    )
