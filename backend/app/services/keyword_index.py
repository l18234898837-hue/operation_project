import re

import jieba


TECHNICAL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9-])(?:[A-Za-z]+-?\d+[A-Za-z]*|\d+[A-Za-z]+|[A-Z]{2,})(?![A-Za-z0-9-])"
)
CUSTOM_TERMS = ("故障码",)

for term in CUSTOM_TERMS:
    jieba.add_word(term)


def normalize_query(query: str) -> str:
    return " ".join(query.split())


def build_keyword_text(indexed_text: str) -> str:
    normalized_text = normalize_query(indexed_text)
    tokens: list[str] = []
    cursor = 0

    for match in TECHNICAL_TOKEN_RE.finditer(normalized_text):
        tokens.extend(_segment_text(normalized_text[cursor : match.start()]))
        tokens.append(match.group(0))
        cursor = match.end()

    tokens.extend(_segment_text(normalized_text[cursor:]))
    return " ".join(_dedupe(tokens))


def _segment_text(text: str) -> list[str]:
    return [
        token
        for token in (part.strip() for part in jieba.cut_for_search(text))
        if token and re.search(r"[\w\u4e00-\u9fff]", token) and not token.isascii()
    ]


def _dedupe(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)

    return deduped
