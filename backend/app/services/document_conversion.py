from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DocumentConversionError(RuntimeError):
    pass


class MarkdownConverter(Protocol):
    def convert(self, source_path: Path) -> str:
        ...


@dataclass(frozen=True)
class MarkItDownConverter:
    def convert(self, source_path: Path) -> str:
        from markitdown import MarkItDown

        result = MarkItDown().convert(str(source_path))
        text_content = getattr(result, "text_content", None)
        if not isinstance(text_content, str) or not text_content.strip():
            raise DocumentConversionError("MarkItDown did not produce Markdown text")
        return text_content


TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


def convert_document_to_markdown(
    source_path: Path,
    markdown_path: Path,
    converter: MarkdownConverter | None = None,
) -> Path:
    if not source_path.is_file():
        raise DocumentConversionError(
            f"source file does not exist, cannot convert to Markdown: {source_path}"
        )

    extension = source_path.suffix.lower()
    try:
        if extension in TEXT_EXTENSIONS:
            markdown_text = source_path.read_bytes().decode("utf-8")
        else:
            markdown_text = (converter or MarkItDownConverter()).convert(source_path)
    except UnicodeDecodeError as exc:
        raise DocumentConversionError("Text files must use UTF-8 encoding") from exc
    except DocumentConversionError:
        raise
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        raise DocumentConversionError(message) from exc

    if not isinstance(markdown_text, str) or not markdown_text.strip():
        raise DocumentConversionError("MarkItDown did not produce Markdown text")

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_bytes(markdown_text.encode("utf-8"))
    return markdown_path
