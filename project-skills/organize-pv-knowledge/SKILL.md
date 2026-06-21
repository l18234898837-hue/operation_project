---
name: organize-pv-knowledge
description: Organize messy photovoltaic operation and maintenance materials into clean knowledge-base documents. Use when Codex needs to process PV O&M DOCX files, WeChat article extracts, PPT screenshots, OCR text, fault photos, or mixed source notes into categorized source-grounded documents and image asset tables for knowledge-base ingestion.
---

# Organize PV Knowledge

Use this skill to turn scattered PV O&M material into a maintainable knowledge base.

## Workflow

1. **Extract source material**
   - Extract DOCX paragraphs, URLs, and embedded images.
   - Try to read linked article text when accessible.
   - Separate text, OCR candidates, fault photos, device photos, decorative images, and attachments.
   - Use `scripts/extract_docx_assets.py` for DOCX preprocessing.
   - Preserve an extraction manifest so coverage can be checked against the source.

2. **Classify into the 9 formal knowledge documents**
   - Read `references/taxonomy.md`.
   - Place each finalized knowledge item into exactly one primary formal document and optional cross-reference notes.
   - Use the intermediate document area only for PPT pages, OCR text, or screenshots that are not yet recognized or classified.
   - Prefer user question scenarios over original article order.

3. **Integrate text into topic documents**
   - Do not preserve source links as body content unless the user explicitly wants citations.
   - Rewrite article text, DOCX notes, OCR text, and PPT text into structured knowledge.
   - Remove marketing phrases, repeated intros, irrelevant commentary, and unsupported claims.
   - Do not invent, expand, or generalize beyond the extracted material.
   - Do not shorten away source knowledge points; classify and preserve all operationally useful content.

4. **Handle images**
   - Read `references/image-policy.md`.
   - Insert useful images into the body semantically with `(见图 IMG_###)`.
   - Keep only fault photos and device photos in the image asset table.
   - OCR text screenshots and PPT pages before integrating their content.
   - Do not list successfully recognized text screenshots in the image asset table.
   - Archive decorative or cover images; do not include them in the knowledge base.

5. **Write each topic document**
   - Read `references/document-template.md`.
   - Use consistent sections: scope and extracted knowledge by topic.
   - Keep each fault point granular enough for retrieval, but do not create artificial questions and answers.

6. **Validate**
   - Confirm all 9 formal knowledge documents exist.
   - Confirm intermediate documents are stored outside the formal knowledge document root or in a clearly marked intermediate folder.
   - Confirm the image asset table exists and contains only fault photos/device photos.
   - Confirm in-body `IMG_###` references for text screenshots are not required in the image table when their OCR text has been merged.
   - Confirm no standalone source-link section was added.
   - Confirm topic documents use the shared structure, avoid raw article dumps, and include all useful source topics.

## Output Rules

- Produce `9` formal topic documents plus one image asset table.
- Keep OCR/PPT staging materials as intermediate documents, not as formal knowledge-base documents.
- Do not create a source index table unless the user asks for traceability.
- Do not dump all pictures at the end of a document.
- Do not use original links, titles, or source ordering as the primary organization.
- Do not add `易混淆问题` or `问答知识卡片` sections.
- Do not add `待补充`, `待OCR`, or process-note sections to final knowledge documents.
- Do not fabricate details that are not present in the source material.
- Use concise, operational language suitable for a PV O&M knowledge assistant.

## Resources

- `references/taxonomy.md`: fixed 10-document classification system.
- `references/document-template.md`: standard document structure and writing rules.
- `references/image-policy.md`: OCR, image classification, and body-reference rules.
- `scripts/extract_docx_assets.py`: DOCX text, URL, and image extraction helper.
