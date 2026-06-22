from app.services.keyword_index import build_keyword_text, normalize_query


def test_build_keyword_text_keeps_heading_terms_and_technical_tokens():
    indexed_text = (
        "逆变器故障与维护 > 常见故障与处理 > PV 过压\n"
        "检查 PV1 电压、直流侧接线和故障码 E001。"
    )

    keyword_text = build_keyword_text(indexed_text)
    tokens = keyword_text.split()

    for term in ["逆变器", "故障", "维护", "常见", "处理", "PV", "过压", "检查", "PV1", "电压", "直流", "接线", "故障码", "E001"]:
        assert term in tokens


def test_normalize_query_trims_and_compacts_whitespace():
    assert normalize_query("  PV1\t  电压\n\n E001  ") == "PV1 电压 E001"


def test_build_keyword_text_deduplicates_preserving_first_occurrence_order():
    keyword_text = build_keyword_text("PV 过压 PV 过压\n检查 PV1 后复查 PV1。")

    assert keyword_text.split() == ["PV", "过压", "检查", "PV1", "后", "复查"]


def test_build_keyword_text_handles_mixed_case_technical_tokens():
    keyword_text = build_keyword_text(
        "SVG 与 10kV 母线检查\nQF1 合闸，INV-01 输出异常，pv1 复测。"
    )
    tokens = keyword_text.split()

    for token in ["SVG", "10kV", "QF1", "INV-01", "pv1"]:
        assert token in tokens


def test_build_keyword_text_does_not_keep_ordinary_english_prose():
    keyword_text = build_keyword_text(
        "normal text and words before SVG 10kV QF1 INV-01 PV1 E001 pv1"
    )
    tokens = keyword_text.split()

    for word in ["normal", "text", "and", "words", "before"]:
        assert word not in tokens

    for token in ["SVG", "10kV", "QF1", "INV-01", "PV1", "E001", "pv1"]:
        assert token in tokens
