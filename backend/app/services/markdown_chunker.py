import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarkdownChunk:
    heading_path: str
    section_title: str | None
    raw_text: str
    clean_text: str
    indexed_text: str
    char_count: int
    metadata: dict[str, Any]


@dataclass
class _Section:
    level: int
    title: str | None
    content_lines: list[str] = field(default_factory=list)
    children: list["_Section"] = field(default_factory=list)
    parent: "_Section | None" = None


@dataclass
class _ChunkUnit:
    sections: list[_Section]

    @property
    def heading_section(self) -> _Section:
        return self.sections[0]


@dataclass
class _Block:
    text: str
    boundary: bool = False


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_FAULT_TOPIC_SPLIT_RE = re.compile(r"[：:－—–-]")
_MIN_DIRECT_CHARS = 250
_MAX_DIRECT_CHARS = 1000
_LONG_TARGET_CHARS = 800


def clean_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n")]
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def chunk_markdown(markdown: str, source_title: str) -> list[MarkdownChunk]:
    root = _parse_sections(markdown)
    chunks: list[MarkdownChunk] = []

    for unit in _merge_short_sections(_base_sections(root)):
        chunks.extend(_chunks_for_unit(unit, source_title))

    return chunks


def _parse_sections(markdown: str) -> _Section:
    root = _Section(level=0, title=None)
    stack: list[_Section] = [root]

    for line in markdown.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1].level >= level:
                stack.pop()
            parent = stack[-1] if stack else root
            section = _Section(level=level, title=title, parent=parent)
            parent.children.append(section)
            stack.append(section)
        else:
            stack[-1].content_lines.append(line)

    return root


def _base_sections(root: _Section) -> list[_Section]:
    result: list[_Section] = []
    for child in root.children:
        _collect_base_sections(child, result)
    return result


def _collect_base_sections(section: _Section, result: list[_Section]) -> None:
    if section.level in (3, 4):
        result.append(section)
        return

    if not section.children and clean_text("\n".join(section.content_lines)):
        result.append(section)
        return

    for child in section.children:
        _collect_base_sections(child, result)


def _merge_short_sections(sections: list[_Section]) -> list[_ChunkUnit]:
    units: list[_ChunkUnit] = []
    index = 0

    while index < len(sections):
        section = sections[index]
        group = [section]
        topic = _fault_topic(section)
        index += 1

        while index < len(sections):
            candidate = sections[index]
            if not _can_merge_short_sibling(group[-1], candidate, topic):
                break
            group.append(candidate)
            index += 1

        units.append(_ChunkUnit(sections=group))

    return units


def _can_merge_short_sibling(
    previous: _Section, candidate: _Section, topic: str
) -> bool:
    return (
        previous.parent is candidate.parent
        and previous.level == candidate.level
        and _is_short_section(previous)
        and _is_short_section(candidate)
        and _fault_topic(candidate) == topic
    )


def _chunks_for_unit(unit: _ChunkUnit, source_title: str) -> list[MarkdownChunk]:
    text = _unit_text(unit)
    char_count = _chinese_char_count(text)
    if not text:
        return []

    if char_count > _MAX_DIRECT_CHARS:
        return _split_long_unit(unit, source_title)

    reason = "direct_section" if char_count >= _MIN_DIRECT_CHARS else "short_section"
    if len(unit.sections) > 1:
        reason = "merged_short_sections"

    return [
        _make_chunk(
            unit=unit,
            source_title=source_title,
            text=text,
            split_reason=reason,
            part_index=0,
            part_count=1,
            overlap_chars=0,
        )
    ]


def _unit_text(unit: _ChunkUnit) -> str:
    parts: list[str] = []
    content_without_parent = _unit_text_without_parent(unit)
    if _chinese_char_count(content_without_parent) < _MIN_DIRECT_CHARS:
        parent_text = _common_parent_text(unit.sections)
        if parent_text:
            parts.append(parent_text)

    if content_without_parent:
        parts.append(content_without_parent)

    return clean_text("\n\n".join(parts))


def _unit_text_without_parent(unit: _ChunkUnit) -> str:
    if len(unit.sections) == 1:
        return _section_text(unit.sections[0])

    parts: list[str] = []
    for section in unit.sections:
        section_text = _section_text(section)
        if section_text:
            parts.append(f"{'#' * section.level} {section.title}\n\n{section_text}")
    return clean_text("\n\n".join(parts))


def _section_text(section: _Section) -> str:
    parts: list[str] = []
    own_text = clean_text("\n".join(section.content_lines))
    if own_text:
        parts.append(own_text)

    for child in section.children:
        child_text = _section_text(child)
        if child_text:
            parts.append(f"{'#' * child.level} {child.title}\n\n{child_text}")

    return clean_text("\n\n".join(parts))


def _split_long_unit(unit: _ChunkUnit, source_title: str) -> list[MarkdownChunk]:
    blocks = _unit_blocks(unit)
    grouped: list[str] = []
    current: list[str] = []
    current_count = 0

    for block in blocks:
        block_count = _chinese_char_count(block.text)
        hits_boundary = block.boundary and current
        would_exceed = current and current_count + block_count > _LONG_TARGET_CHARS
        if hits_boundary or would_exceed:
            grouped.append(clean_text("\n\n".join(current)))
            current = []
            current_count = 0
        current.append(block.text)
        current_count += block_count
        if block.boundary:
            grouped.append(clean_text("\n\n".join(current)))
            current = []
            current_count = 0

    if current:
        grouped.append(clean_text("\n\n".join(current)))

    if len(grouped) == 1 and _chinese_char_count(grouped[0]) > _MAX_DIRECT_CHARS:
        grouped = _split_by_length(grouped[0], _LONG_TARGET_CHARS)

    return [
        _make_chunk(
            unit=unit,
            source_title=source_title,
            text=part,
            split_reason="long_section",
            part_index=index,
            part_count=len(grouped),
            overlap_chars=0,
        )
        for index, part in enumerate(grouped)
    ]


def _unit_blocks(unit: _ChunkUnit) -> list[_Block]:
    if len(unit.sections) > 1:
        return [
            _Block(f"{'#' * section.level} {section.title}\n\n{_section_text(section)}")
            for section in unit.sections
            if _section_text(section)
        ]

    section = unit.sections[0]
    blocks: list[_Block] = []
    content_without_parent = _unit_text_without_parent(unit)
    if _chinese_char_count(content_without_parent) < _MIN_DIRECT_CHARS:
        parent_text = _common_parent_text(unit.sections)
        if parent_text:
            blocks.extend(_text_blocks(parent_text))

    own_text = clean_text("\n".join(section.content_lines))
    if own_text:
        blocks.extend(_text_blocks(own_text))

    for child in section.children:
        child_text = _section_text(child)
        if not child_text:
            continue
        blocks.extend(_child_section_blocks(child))

    if not blocks:
        blocks = _text_blocks(content_without_parent)

    return blocks


def _text_blocks(text: str) -> list[_Block]:
    blocks: list[_Block] = []
    current: list[str] = []
    current_mode: str | None = None

    def flush() -> None:
        nonlocal current, current_mode
        if not current:
            return
        block_text = clean_text("\n".join(current))
        if current_mode == "list":
            blocks.extend(_list_blocks(current))
        elif _chinese_char_count(block_text) > _MAX_DIRECT_CHARS:
            blocks.extend(_Block(part) for part in _split_by_length(block_text, _LONG_TARGET_CHARS))
        else:
            blocks.append(_Block(block_text))
        current = []
        current_mode = None

    for line in clean_text(text).splitlines():
        if not line.strip():
            flush()
            continue

        mode = "list" if _LIST_ITEM_RE.match(line) else "paragraph"
        if current_mode is not None and current_mode != mode:
            flush()
        current.append(line)
        current_mode = mode

    flush()
    return blocks


def _child_section_blocks(section: _Section) -> list[_Block]:
    heading = f"{'#' * section.level} {section.title}"
    content_blocks = _text_blocks(_section_text(section))
    if not content_blocks:
        return []

    result: list[_Block] = []
    current: list[str] = []
    current_count = 0

    def flush() -> None:
        nonlocal current, current_count
        if not current:
            return
        content = clean_text("\n\n".join(current))
        result.append(_Block(f"{heading}\n\n{content}", boundary=True))
        current = []
        current_count = 0

    for block in content_blocks:
        block_count = _chinese_char_count(block.text)
        if current and current_count + block_count > _LONG_TARGET_CHARS:
            flush()
        current.append(block.text)
        current_count += block_count

    flush()
    return result


def _list_blocks(lines: list[str]) -> list[_Block]:
    result: list[_Block] = []
    current: list[str] = []
    current_count = 0

    def flush() -> None:
        nonlocal current, current_count
        if not current:
            return
        result.append(_Block(clean_text("\n".join(current))))
        current = []
        current_count = 0

    for line in lines:
        line_count = _chinese_char_count(line)
        if line_count > _LONG_TARGET_CHARS:
            flush()
            result.extend(_Block(part) for part in _split_list_item(line, _LONG_TARGET_CHARS))
            continue

        if current and current_count + line_count > _LONG_TARGET_CHARS:
            flush()
        current.append(line)
        current_count += line_count

    flush()
    return result


def _split_list_item(line: str, target_chars: int) -> list[str]:
    match = re.match(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+))(.*)$", line)
    if not match:
        return _split_by_length(line, target_chars)

    marker = match.group(1).lstrip()
    body = match.group(2)
    body_target = max(1, target_chars - _chinese_char_count(marker))
    return [f"{marker}{part}" for part in _split_by_length(body, body_target)]


def _split_by_length(text: str, target_chars: int) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    current_count = 0

    for char in text:
        current.append(char)
        if _CHINESE_RE.match(char):
            current_count += 1
        if current_count >= target_chars:
            parts.append(clean_text("".join(current)))
            current = []
            current_count = 0

    if current:
        parts.append(clean_text("".join(current)))

    return parts


def _make_chunk(
    unit: _ChunkUnit,
    source_title: str,
    text: str,
    split_reason: str,
    part_index: int,
    part_count: int,
    overlap_chars: int,
) -> MarkdownChunk:
    clean = clean_text(text)
    section = unit.heading_section
    heading_path = _heading_path(section, source_title)
    return MarkdownChunk(
        heading_path=heading_path,
        section_title=section.title,
        raw_text=text,
        clean_text=clean,
        indexed_text=f"{heading_path}\n{clean}",
        char_count=_chinese_char_count(clean),
        metadata={
            "source_title": source_title,
            "heading_level": section.level,
            "split_reason": split_reason,
            "part_index": part_index,
            "part_count": part_count,
            "overlap_chars": overlap_chars,
            "merged_section_count": len(unit.sections),
        },
    )


def _heading_path(section: _Section, source_title: str) -> str:
    titles: list[str] = []
    current: _Section | None = section
    has_h1 = False
    while current is not None:
        if current.title:
            titles.append(current.title)
            has_h1 = has_h1 or current.level == 1
        current = current.parent
    if not has_h1 and source_title:
        titles.append(source_title)
    return " > ".join(reversed(titles))


def _chinese_char_count(text: str) -> int:
    return len(_CHINESE_RE.findall(text))


def _is_short_section(section: _Section) -> bool:
    return _chinese_char_count(_section_text(section)) < _MIN_DIRECT_CHARS


def _fault_topic(section: _Section) -> str:
    title = section.title or ""
    if title in {"现象", "处理", "原因", "措施", "排查", "恢复"} and section.parent:
        title = section.parent.title or title
    return _FAULT_TOPIC_SPLIT_RE.split(title, maxsplit=1)[0].strip()


def _common_parent_text(sections: list[_Section]) -> str:
    if not sections:
        return ""
    parent = sections[0].parent
    if parent is None or any(section.parent is not parent for section in sections):
        return ""
    return clean_text("\n".join(parent.content_lines))
