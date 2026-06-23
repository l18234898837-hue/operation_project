import type { DocumentCategory, DocumentItem } from "../types/document";

export const baseDocumentCategories: Array<Omit<DocumentCategory, "count">> = [
  { key: "all", label: "全部文档" },
  { key: "inverter", label: "逆变器" },
  { key: "inspection", label: "光伏电站巡检" },
  { key: "grid-quality", label: "并网与电能质量" },
  { key: "modules", label: "组件与阵列" },
  { key: "manual", label: "运维手册" },
  { key: "cases", label: "故障案例" },
  { key: "standards", label: "技术标准" },
  { key: "uncategorized", label: "未分类" }
];

export const mockDocuments: DocumentItem[] = [
  {
    id: "doc-inverter-manual",
    name: "逆变器运维手册.pdf",
    type: "PDF",
    category: "inverter",
    parseStatus: "processing",
    enableStatus: "enabled",
    updatedAt: "2024-05-20 14:30:22",
    failureReason: null,
    progress: 60
  },
  {
    id: "doc-inspection-spec",
    name: "电站巡检规范.docx",
    type: "Word",
    category: "inspection",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-19 09:15:33",
    failureReason: null,
    progress: 100
  },
  {
    id: "doc-grid-failure",
    name: "并网故障处理清单.xlsx",
    type: "Excel",
    category: "grid-quality",
    parseStatus: "failed",
    enableStatus: "disabled",
    updatedAt: "2024-05-18 16:45:11",
    failureReason: "表格结构不完整，缺少并网保护定值列",
    progress: null
  },
  {
    id: "doc-station-design",
    name: "光伏电站设计规范.pdf",
    type: "PDF",
    category: "standards",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-18 11:22:07",
    failureReason: null,
    progress: 100
  },
  {
    id: "doc-transformer-guide",
    name: "箱变维护指南.pdf",
    type: "PDF",
    category: "manual",
    parseStatus: "failed",
    enableStatus: "disabled",
    updatedAt: "2024-05-17 10:05:44",
    failureReason: "文件页码解析失败，疑似扫描件缺少文本层",
    progress: null
  },
  {
    id: "doc-pv-faq",
    name: "光伏系统常见问题解答.docx",
    type: "Word",
    category: "manual",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-16 17:20:31",
    failureReason: null,
    progress: 100
  },
  {
    id: "doc-module-params",
    name: "组件参数对照表.xlsx",
    type: "Excel",
    category: "modules",
    parseStatus: "processing",
    enableStatus: "disabled",
    updatedAt: "2024-05-16 09:18:55",
    failureReason: null,
    progress: 20
  },
  {
    id: "doc-quality-report",
    name: "电能质量分析报告.pdf",
    type: "PDF",
    category: "grid-quality",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-15 15:33:28",
    failureReason: null,
    progress: 100
  },
  {
    id: "doc-temperature-case",
    name: "汇流箱温度异常案例.docx",
    type: "Word",
    category: "cases",
    parseStatus: "failed",
    enableStatus: "disabled",
    updatedAt: "2024-05-15 10:11:06",
    failureReason: "图片文字识别失败，建议重新导出可复制文本版本",
    progress: null
  },
  {
    id: "doc-alarm-code",
    name: "逆变器报警代码表.xlsx",
    type: "Excel",
    category: "inverter",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-14 16:08:19",
    failureReason: null,
    progress: 100
  },
  {
    id: "doc-cleaning-plan",
    name: "组件清洗作业计划.md",
    type: "Markdown",
    category: "modules",
    parseStatus: "uploaded",
    enableStatus: "disabled",
    updatedAt: "2024-05-14 08:30:00",
    failureReason: null,
    progress: 0
  },
  {
    id: "doc-patrol-template",
    name: "日常巡检记录模板.txt",
    type: "TXT",
    category: "inspection",
    parseStatus: "ready",
    enableStatus: "enabled",
    updatedAt: "2024-05-13 18:42:10",
    failureReason: null,
    progress: 100
  }
];
