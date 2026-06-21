#!/usr/bin/env python3
"""Extract paragraphs, URLs, and embedded images from a DOCX file."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def paragraph_texts(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    texts: list[str] = []
    for pnode in root.findall(".//w:p", NS):
        text = "".join(t.text or "" for t in pnode.findall(".//w:t", NS)).strip()
        if text:
            texts.append(text)
    return texts


def extract_images(docx_path: Path, image_dir: Path) -> list[tuple[str, str]]:
    image_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str]] = []
    with zipfile.ZipFile(docx_path) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/") and not n.endswith("/")]
        for index, member in enumerate(media, 1):
            suffix = Path(member).suffix.lower() or ".bin"
            image_id = f"IMG_{index:03d}"
            out_path = image_dir / f"{image_id}{suffix}"
            with zf.open(member) as src, out_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            rows.append((image_id, str(out_path.as_posix())))
    return rows


def write_outputs(docx_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = paragraph_texts(docx_path)
    urls = re.findall(r"https?://[^\s]+", "\n".join(texts))
    image_rows = extract_images(docx_path, out_dir / "images")

    (out_dir / "paragraphs.txt").write_text("\n".join(texts), encoding="utf-8")
    (out_dir / "urls.txt").write_text("\n".join(urls), encoding="utf-8")

    with (out_dir / "image_assets_seed.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["图片编号", "图片类型", "所属主题文档", "正文引用位置", "图片存储路径", "OCR文本", "人工校对文本", "图片说明", "是否入库", "备注"])
        for image_id, path in image_rows:
            writer.writerow([image_id, "待分类", "", "", path, "", "", "", "待定", "从DOCX内嵌图片提取"])

    print(f"paragraphs: {len(texts)}")
    print(f"urls: {len(urls)}")
    print(f"images: {len(image_rows)}")
    print(f"output: {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    write_outputs(args.docx, args.out)


if __name__ == "__main__":
    main()
