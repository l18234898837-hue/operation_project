export type MarkdownInline =
  | { type: "text"; text: string }
  | { type: "strong"; text: string }
  | { type: "code"; text: string };

export type MarkdownBlock =
  | { type: "paragraph"; inlines: MarkdownInline[] }
  | { type: "heading"; level: 1 | 2 | 3 | 4; inlines: MarkdownInline[] }
  | { type: "list"; kind: "ordered" | "unordered"; items: MarkdownInline[][] }
  | { type: "code"; code: string };

function parseInlineMarkdown(text: string): MarkdownInline[] {
  const tokens: MarkdownInline[] = [];
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      tokens.push({ type: "text", text: text.slice(cursor, match.index) });
    }

    if (match[2]) {
      tokens.push({ type: "strong", text: match[2] });
    } else if (match[3]) {
      tokens.push({ type: "code", text: match[3] });
    }

    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    tokens.push({ type: "text", text: text.slice(cursor) });
  }

  return tokens.length > 0 ? tokens : [{ type: "text", text }];
}

function listMarker(line: string) {
  const unordered = line.match(/^\s*[-*]\s+(.+)$/);

  if (unordered) {
    return { kind: "unordered" as const, content: unordered[1] };
  }

  const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);

  if (ordered) {
    return { kind: "ordered" as const, content: ordered[1] };
  }

  return null;
}

function pushParagraph(blocks: MarkdownBlock[], lines: string[]) {
  const text = lines.join("\n").trim();

  if (text) {
    blocks.push({ type: "paragraph", inlines: parseInlineMarkdown(text) });
  }
}

function pushList(blocks: MarkdownBlock[], kind: "ordered" | "unordered", items: string[]) {
  if (items.length > 0) {
    blocks.push({ type: "list", kind, items: items.map(parseInlineMarkdown) });
  }
}

export function parseAssistantMarkdown(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const paragraphLines: string[] = [];
  let listKind: "ordered" | "unordered" | null = null;
  let listItems: string[] = [];
  let codeLines: string[] | null = null;

  function flushTextBlocks() {
    pushParagraph(blocks, paragraphLines.splice(0));

    if (listKind) {
      pushList(blocks, listKind, listItems);
      listKind = null;
      listItems = [];
    }
  }

  for (const rawLine of markdown.split(/\r?\n/)) {
    const line = rawLine.trimEnd();

    if (line.trim().startsWith("```")) {
      if (codeLines) {
        blocks.push({ type: "code", code: codeLines.join("\n") });
        codeLines = null;
      } else {
        flushTextBlocks();
        codeLines = [];
      }

      continue;
    }

    if (codeLines) {
      codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      flushTextBlocks();
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);

    if (heading) {
      flushTextBlocks();
      blocks.push({
        type: "heading",
        level: heading[1].length as 1 | 2 | 3 | 4,
        inlines: parseInlineMarkdown(heading[2])
      });
      continue;
    }

    const marker = listMarker(line);

    if (marker) {
      pushParagraph(blocks, paragraphLines.splice(0));

      if (listKind && listKind !== marker.kind) {
        pushList(blocks, listKind, listItems);
        listItems = [];
      }

      listKind = marker.kind;
      listItems.push(marker.content);
      continue;
    }

    if (listKind && /^\s{2,}\S/.test(rawLine) && listItems.length > 0) {
      listItems[listItems.length - 1] += ` ${line.trim()}`;
      continue;
    }

    if (listKind) {
      pushList(blocks, listKind, listItems);
      listKind = null;
      listItems = [];
    }

    paragraphLines.push(line);
  }

  if (codeLines) {
    blocks.push({ type: "code", code: codeLines.join("\n") });
  }

  pushParagraph(blocks, paragraphLines);

  if (listKind) {
    pushList(blocks, listKind, listItems);
  }

  return blocks;
}
