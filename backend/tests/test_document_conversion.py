from pathlib import Path

import pytest

from app.services.document_conversion import (
    DocumentConversionError,
    convert_document_to_markdown,
)


class FakeConverter:
    def __init__(self, markdown="# Converted\n\nBody", error=None):
        self.markdown = markdown
        self.error = error
        self.calls = []

    def convert(self, source_path: Path) -> str:
        self.calls.append(source_path)
        if self.error is not None:
            raise self.error
        return self.markdown


def test_text_file_writes_utf8_content_to_markdown_target(tmp_path):
    source = tmp_path / "manual.txt"
    target = tmp_path / "markdown" / "manual.md"
    source.write_text("# Manual\n\nPlain text", encoding="utf-8")

    result = convert_document_to_markdown(source, target)

    assert result == target
    assert target.read_text(encoding="utf-8") == "# Manual\n\nPlain text"


def test_non_text_file_uses_converter_and_writes_markdown(tmp_path):
    source = tmp_path / "manual.pdf"
    target = tmp_path / "markdown" / "manual.md"
    source.write_bytes(b"%PDF fake")
    converter = FakeConverter("# PDF Manual\n\nConverted text")

    result = convert_document_to_markdown(source, target, converter=converter)

    assert result == target
    assert converter.calls == [source]
    assert target.read_text(encoding="utf-8") == "# PDF Manual\n\nConverted text"


def test_missing_source_fails_before_conversion(tmp_path):
    source = tmp_path / "missing.pdf"
    target = tmp_path / "markdown" / "missing.md"
    converter = FakeConverter()

    with pytest.raises(DocumentConversionError, match="source file does not exist"):
        convert_document_to_markdown(source, target, converter=converter)

    assert converter.calls == []
    assert not target.exists()


def test_non_utf8_text_file_raises_readable_conversion_error(tmp_path):
    source = tmp_path / "bad.txt"
    target = tmp_path / "markdown" / "bad.md"
    source.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(DocumentConversionError, match="UTF-8"):
        convert_document_to_markdown(source, target)

    assert not target.exists()


@pytest.mark.parametrize("markdown", ["", "   \n\t"])
def test_empty_converter_output_raises_readable_conversion_error(tmp_path, markdown):
    source = tmp_path / "manual.docx"
    target = tmp_path / "markdown" / "manual.md"
    source.write_bytes(b"fake docx")

    with pytest.raises(DocumentConversionError, match="did not produce Markdown"):
        convert_document_to_markdown(source, target, converter=FakeConverter(markdown))

    assert not target.exists()


def test_converter_failure_raises_readable_conversion_error(tmp_path):
    source = tmp_path / "manual.xlsx"
    target = tmp_path / "markdown" / "manual.md"
    source.write_bytes(b"fake workbook")

    with pytest.raises(DocumentConversionError, match="converter unavailable"):
        convert_document_to_markdown(
            source,
            target,
            converter=FakeConverter(error=RuntimeError("converter unavailable")),
        )

    assert not target.exists()
