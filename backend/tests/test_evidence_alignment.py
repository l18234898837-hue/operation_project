from types import SimpleNamespace

from app.services.evidence_alignment import check_evidence_directly_supports_question


def test_evidence_alignment_blocks_missing_question_topic_terms():
    result = check_evidence_directly_supports_question(
        "逆变器在监控平台上显示通讯中断，现场应该怎么排查？",
        [
            SimpleNamespace(
                heading_path="01_逆变器故障与维护 > 3.2 电网过压或欠压",
                clean_text="电网电压过高或过低会导致逆变器保护停机。",
            )
        ],
    )

    assert result.directly_supported is False
    assert result.reason == "missing_topic_terms"
    assert result.missing_topics == ("communication",)


def test_evidence_alignment_allows_matching_question_topic_terms():
    result = check_evidence_directly_supports_question(
        "逆变器在监控平台上显示通讯中断，现场应该怎么排查？",
        [
            SimpleNamespace(
                heading_path="01_通讯故障 > 逆变器离线",
                clean_text="逆变器离线时，应检查监控平台、采集器、RS485 通信链路和网络状态。",
            )
        ],
    )

    assert result.directly_supported is True
    assert result.reason == "topic_terms_matched"
    assert "communication" in result.question_topics
    assert "communication" in result.evidence_topics


def test_evidence_alignment_allows_questions_without_topic_terms():
    result = check_evidence_directly_supports_question(
        "下一步怎么处理？",
        [
            SimpleNamespace(
                heading_path="03_线缆接头与绝缘故障 > 5. 端子与接头问题",
                clean_text="接头松动、氧化或接触不良可能导致温度升高。",
            )
        ],
    )

    assert result.directly_supported is True
    assert result.reason == "no_topic_terms_required"
