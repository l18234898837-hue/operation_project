export type DocumentType = "PDF" | "Word" | "Excel" | "Markdown" | "TXT";

export type DocumentParseStatus = "uploaded" | "processing" | "ready" | "failed";

export type DocumentEnableStatus = "enabled" | "disabled";

export type DocumentTreeNodeKind = "all" | "status" | "category" | "type";

export interface DocumentTreeNode {
  id: string;
  kind: DocumentTreeNodeKind;
  label: string;
  count: number;
  value: string;
}

export type DocumentCategoryKey =
  | "all"
  | "inverter"
  | "inspection"
  | "grid-quality"
  | "modules"
  | "manual"
  | "cases"
  | "standards"
  | "uncategorized"
  | "processing"
  | "failed"
  | "enabled"
  | "disabled";

export interface DocumentItem {
  id: string;
  name: string;
  type: DocumentType;
  category: Exclude<
    DocumentCategoryKey,
    "all" | "processing" | "failed" | "enabled" | "disabled"
  >;
  parseStatus: DocumentParseStatus;
  enableStatus: DocumentEnableStatus;
  updatedAt: string;
  failureReason: string | null;
  progress: number | null;
}

export interface DocumentCategory {
  key: DocumentCategoryKey;
  label: string;
  count: number;
}

export interface DocumentFilters {
  category: DocumentCategoryKey;
  keyword: string;
  type: DocumentType | "all";
  parseStatus: DocumentParseStatus | "all";
  enableStatus: DocumentEnableStatus | "all";
  page: number;
  pageSize: number;
}

export interface DocumentSummary {
  total: number;
  processing: number;
  failed: number;
  enabled: number;
}

export interface ParseTaskSummary {
  id: string;
  status: "pending" | "running" | "success" | "failed";
  parserName: string | null;
  retryCount: number;
  durationMs: number | null;
  errorMessage: string | null;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface SegmentPreview {
  id: string;
  chunkIndex: number;
  headingPath: string | null;
  sectionTitle: string | null;
  charCount: number;
  hasEmbedding: boolean;
}

export interface DocumentDetail {
  item: DocumentItem;
  sourcePath: string | null;
  markdownPath: string | null;
  fileSha256: string | null;
  segmentCount: number;
  metadata: Record<string, unknown>;
  latestTask: ParseTaskSummary | null;
  recentTasks: ParseTaskSummary[];
  segmentPreview: SegmentPreview[];
}
