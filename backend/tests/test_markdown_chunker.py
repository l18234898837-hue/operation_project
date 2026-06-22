from app.services.markdown_chunker import MarkdownChunk, chunk_markdown, clean_text


def zh(char_count: int, token: str = "测") -> str:
    return token * char_count


def test_oversized_child_heading_split_repeats_child_heading_context():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

#### 现象

{zh(420, "现")}

{zh(420, "象")}

- {zh(120, "甲")}
- {zh(120, "乙")}

#### 处理

恢复前复核每路组串电压。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")
    phenomenon_chunks = [
        chunk
        for chunk in chunks
        if "现现" in chunk.clean_text or "象象" in chunk.clean_text
    ]

    assert len(phenomenon_chunks) >= 2
    assert all("#### 现象" in chunk.clean_text for chunk in phenomenon_chunks)
    assert all("#### 处理" not in chunk.clean_text for chunk in phenomenon_chunks)


def test_oversized_list_group_batches_items_without_breaking_list_lines():
    items = "\n".join(f"- 项目{i}{zh(90, '项')}" for i in range(14))
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

{items}
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) >= 2
    for chunk in chunks:
        for line in chunk.clean_text.splitlines():
            if line:
                assert line.startswith("- ") or line.startswith("#")


def test_single_oversized_list_item_split_preserves_marker_on_each_part():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

- {zh(1700, "项")}
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) >= 2
    for chunk in chunks:
        item_lines = [line for line in chunk.clean_text.splitlines() if "项项" in line]
        assert item_lines
        assert all(line.startswith("- ") for line in item_lines)


def test_long_split_keeps_parent_context_when_parent_text_makes_short_unit_long():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理

父级说明{zh(1005, "父")}

### PV 过压

短处理说明。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) >= 2
    assert any("父级说明" in chunk.clean_text for chunk in chunks)
    assert any("短处理说明" in chunk.clean_text for chunk in chunks)


def test_heading_path_and_indexed_text_prefix_for_nested_headings():
    markdown = """
# 逆变器故障与维护

总说明。

## 常见故障与处理

处理原则。

### PV 过压

检查组串电压，确认开路电压是否超过逆变器允许范围。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 1
    assert isinstance(chunks[0], MarkdownChunk)
    assert chunks[0].heading_path == "逆变器故障与维护 > 常见故障与处理 > PV 过压"
    assert chunks[0].section_title == "PV 过压"
    assert chunks[0].indexed_text.startswith(
        "逆变器故障与维护 > 常见故障与处理 > PV 过压\n"
    )
    assert "检查组串电压" in chunks[0].indexed_text
    assert clean_text("  A  \n\n\n  B  ") == "A\n\nB"


def test_long_section_split_does_not_cross_into_next_fault_heading():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

第一段{zh(520, "压")}

第二段{zh(520, "伏")}

### 绝缘阻抗低

排查对地绝缘，检查线缆破皮与端子进水。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")
    over_voltage_chunks = [
        chunk for chunk in chunks if chunk.section_title == "PV 过压"
    ]
    insulation_chunks = [
        chunk for chunk in chunks if chunk.section_title == "绝缘阻抗低"
    ]

    assert len(over_voltage_chunks) == 2
    assert len(insulation_chunks) == 1
    assert all("绝缘阻抗低" not in chunk.clean_text for chunk in over_voltage_chunks)
    assert all("排查对地绝缘" not in chunk.clean_text for chunk in over_voltage_chunks)
    assert insulation_chunks[0].heading_path.endswith("绝缘阻抗低")


def test_short_same_topic_sections_merge_but_different_fault_topic_does_not_merge():
    markdown = """
# 逆变器故障与维护
## 常见故障与处理
### PV 过压
#### 现象

报 PV 电压高，设备停止并网。

#### 处理

核对组串开路电压，减少串联组件数量。

### 绝缘阻抗低

检查直流线缆与组件边框接地情况。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")
    pv_chunks = [chunk for chunk in chunks if "PV 过压" in chunk.heading_path]
    insulation_chunks = [
        chunk for chunk in chunks if "绝缘阻抗低" in chunk.heading_path
    ]

    assert len(pv_chunks) == 1
    assert "报 PV 电压高" in pv_chunks[0].clean_text
    assert "核对组串开路电压" in pv_chunks[0].clean_text
    assert "检查直流线缆" not in pv_chunks[0].clean_text
    assert len(insulation_chunks) == 1


def test_section_between_250_and_1000_chinese_chars_is_one_chunk():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

{zh(320)}
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 1
    assert chunks[0].section_title == "PV 过压"
    assert chunks[0].char_count == 320
    assert chunks[0].clean_text == zh(320)


def test_short_list_style_section_does_not_get_artificial_overlap():
    markdown = """
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

- 断开直流开关。
- 测量每路组串开路电压。
- 恢复接线后观察告警是否消失。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 1
    assert chunks[0].clean_text.count("断开直流开关") == 1
    assert chunks[0].clean_text.count("测量每路组串开路电压") == 1
    assert chunks[0].metadata["split_reason"] == "short_section"
    assert chunks[0].metadata["overlap_chars"] == 0


def test_adjacent_short_same_level_sections_merge_by_fault_topic():
    markdown = """
## 常见故障与处理

本章处理直流侧常见告警。

### PV 过压：现象

逆变器提示 PV 电压高。

### PV 过压：处理

减少串联组件数量，复核开路电压。

### 绝缘阻抗低：现象

提示绝缘阻抗低，禁止并网。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")
    pv_chunks = [chunk for chunk in chunks if "PV 过压" in chunk.heading_path]
    insulation_chunks = [chunk for chunk in chunks if "绝缘阻抗低" in chunk.heading_path]

    assert len(pv_chunks) == 1
    assert pv_chunks[0].heading_path == "维护手册 > 常见故障与处理 > PV 过压：现象"
    assert "本章处理直流侧常见告警" in pv_chunks[0].clean_text
    assert "逆变器提示 PV 电压高" in pv_chunks[0].clean_text
    assert "减少串联组件数量" in pv_chunks[0].clean_text
    assert "提示绝缘阻抗低" not in pv_chunks[0].clean_text
    assert len(insulation_chunks) == 1


def test_adjacent_short_sections_do_not_merge_across_different_fault_topics():
    markdown = """
# 逆变器故障与维护
## 常见故障与处理
### PV 过压：处理

减少串联组件数量。

### 电网过压：处理

检查并网点电压与保护参数。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 2
    assert chunks[0].heading_path.endswith("PV 过压：处理")
    assert "检查并网点电压" not in chunks[0].clean_text
    assert chunks[1].heading_path.endswith("电网过压：处理")


def test_source_title_prefixes_heading_path_when_markdown_has_no_h1():
    markdown = """
## 常见故障与处理
### PV 过压

检查组串电压。
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 1
    assert chunks[0].heading_path == "维护手册 > 常见故障与处理 > PV 过压"
    assert chunks[0].indexed_text.startswith("维护手册 > 常见故障与处理 > PV 过压\n")


def test_long_section_groups_paragraphs_and_list_items_without_crossing_child_headings():
    markdown = f"""
# 逆变器故障与维护
## 常见故障与处理
### PV 过压

#### 现象

{zh(260, "现")}

- {zh(120, "甲")}
- {zh(120, "乙")}

#### 处理

{zh(260, "处")}

- {zh(120, "丙")}
- {zh(120, "丁")}
"""

    chunks = chunk_markdown(markdown, source_title="维护手册")

    assert len(chunks) == 2
    assert all(chunk.section_title == "PV 过压" for chunk in chunks)
    assert "#### 现象" in chunks[0].clean_text
    assert "#### 处理" not in chunks[0].clean_text
    assert 500 <= chunks[0].char_count <= 800
    assert "#### 处理" in chunks[1].clean_text
    assert "#### 现象" not in chunks[1].clean_text
    assert 500 <= chunks[1].char_count <= 800
