import { parseAssistantMarkdown, type MarkdownBlock } from "./markdownRenderer";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const blocks = parseAssistantMarkdown(`### 可能原因
- **组件遮挡**：清理遮挡物
1. **初步筛选**：测量电流
\`\`\`
status=ok
\`\`\``);

type BlocksAreMarkdownBlocks = Assert<IsAssignable<typeof blocks, MarkdownBlock[]>>;
type HeadingBlock = Extract<MarkdownBlock, { type: "heading" }>;
type ListBlock = Extract<MarkdownBlock, { type: "list" }>;
type CodeBlock = Extract<MarkdownBlock, { type: "code" }>;
type HeadingLevelSupportsMarkdown = Assert<IsAssignable<HeadingBlock["level"], 1 | 2 | 3 | 4>>;
type ListKindSupportsMarkdown = Assert<IsAssignable<ListBlock["kind"], "ordered" | "unordered">>;
type CodeBlockCarriesText = Assert<IsAssignable<CodeBlock["code"], string>>;

void (null as unknown as BlocksAreMarkdownBlocks);
void (null as unknown as HeadingLevelSupportsMarkdown);
void (null as unknown as ListKindSupportsMarkdown);
void (null as unknown as CodeBlockCarriesText);
