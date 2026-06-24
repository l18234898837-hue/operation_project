import type { QaLogItem } from "../types/log";

const inverterReferences = [
  {
    rank: 1,
    document_id: "doc-inverter-manual",
    segment_id: "seg-inverter-021",
    heading_path: "逆变器运维手册 > 故障排查 > PV 过压",
    excerpt: "PV 输入电压超过保护阈值时，应检查组串开路电压、环境温度和直流侧接线。",
    rerank_score: 0.91
  },
  {
    rank: 2,
    document_id: "doc-alarm-code",
    segment_id: "seg-alarm-104",
    heading_path: "逆变器报警代码表 > 直流侧告警",
    excerpt: "告警代码 PV-OV 通常与组串配置、组件温升和采样异常有关。",
    rerank_score: 0.86
  }
];

export const mockQaLogs: QaLogItem[] = [
  {
    id: "log-rag-inverter",
    question: "逆变器 PV 过压常见原因有哪些？",
    answerPreview: "常见原因包括组串开路电压偏高、低温工况导致电压抬升、直流侧接线异常以及采样模块故障。",
    answerType: "rag",
    intent: "knowledge_base_qa",
    status: "answered",
    processStatus: "resolved",
    confidence: 0.86,
    traceId: "trace_qa_001",
    referenceCount: 2,
    latencyMs: 1280,
    createdAt: "2024-05-20 14:32:18",
    userName: "张工",
    references: inverterReferences,
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 80 },
      { stage: "retrieve", label: "召回检索", milliseconds: 360 },
      { stage: "rerank", label: "重排", milliseconds: 260 },
      { stage: "generate", label: "生成回答", milliseconds: 580 },
      { stage: "total", label: "总耗时", milliseconds: 1280 }
    ],
    decision: { route: "rag", top_k: 6, threshold: 0.72 },
    knowledgeGap: false,
    gapReason: null
  },
  {
    id: "log-general-power",
    question: "什么是无功功率？",
    answerPreview: "无功功率用于建立电磁场，本身不直接做功，但会影响电压水平和电网稳定性。",
    answerType: "general_llm",
    intent: "general_explanation",
    status: "answered",
    processStatus: "reviewed",
    confidence: 0.74,
    traceId: "trace_qa_002",
    referenceCount: 0,
    latencyMs: 940,
    createdAt: "2024-05-20 11:08:43",
    userName: "李工",
    references: [],
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 70 },
      { stage: "retrieve", label: "召回检索", milliseconds: 0 },
      { stage: "rerank", label: "重排", milliseconds: 0 },
      { stage: "generate", label: "生成回答", milliseconds: 870 },
      { stage: "total", label: "总耗时", milliseconds: 940 }
    ],
    decision: { route: "general_llm", reason: "general_concept" },
    knowledgeGap: false,
    gapReason: null
  },
  {
    id: "log-refused-weather",
    question: "今天上海天气怎么样？",
    answerPreview: "该问题需要实时外部信息，当前系统不接入实时天气数据，因此已拒答。",
    answerType: "refused",
    intent: "realtime_external",
    status: "refused",
    processStatus: "new",
    confidence: null,
    traceId: "trace_qa_003",
    referenceCount: 0,
    latencyMs: 420,
    createdAt: "2024-05-19 17:44:02",
    userName: "王工",
    references: [],
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 120 },
      { stage: "retrieve", label: "召回检索", milliseconds: 0 },
      { stage: "rerank", label: "重排", milliseconds: 0 },
      { stage: "generate", label: "生成回答", milliseconds: 300 },
      { stage: "total", label: "总耗时", milliseconds: 420 }
    ],
    decision: { route: "refused", refusal_reason: "realtime_external" },
    knowledgeGap: true,
    gapReason: "用户期望实时外部数据，当前系统未接入实时数据源"
  },
  {
    id: "log-insufficient-transformer",
    question: "箱变低压侧偶发跳闸怎么定位？",
    answerPreview: "当前知识库证据不足，只能建议先核查保护动作记录、负载曲线和低压侧开关状态。",
    answerType: "none",
    intent: "knowledge_base_qa",
    status: "insufficient_evidence",
    processStatus: "new",
    confidence: 0.38,
    traceId: "trace_qa_004",
    referenceCount: 1,
    latencyMs: 1680,
    createdAt: "2024-05-19 09:27:16",
    userName: "赵工",
    references: [
      {
        rank: 1,
        document_id: "doc-transformer-guide",
        segment_id: "seg-transformer-009",
        heading_path: "箱变维护指南 > 低压侧检查",
        excerpt: "低压侧异常应结合保护动作、负荷趋势和开关温升综合判断。",
        rerank_score: 0.49
      }
    ],
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 92 },
      { stage: "retrieve", label: "召回检索", milliseconds: 610 },
      { stage: "rerank", label: "重排", milliseconds: 280 },
      { stage: "generate", label: "生成回答", milliseconds: 698 },
      { stage: "total", label: "总耗时", milliseconds: 1680 }
    ],
    decision: { route: "none", reason: "evidence_below_threshold", threshold: 0.65 },
    knowledgeGap: true,
    gapReason: "缺少箱变低压侧跳闸专题文档"
  },
  {
    id: "log-low-confidence-module",
    question: "组件热斑会不会导致组串电流波动？",
    answerPreview: "可能会。热斑会改变局部组件工作点，但当前引用片段相关度偏低，建议结合红外巡检记录判断。",
    answerType: "rag",
    intent: "knowledge_base_qa",
    status: "low_confidence",
    processStatus: "reviewed",
    confidence: 0.52,
    traceId: "trace_qa_005",
    referenceCount: 1,
    latencyMs: 1320,
    createdAt: "2024-05-18 18:20:10",
    userName: "陈工",
    references: [
      {
        rank: 1,
        document_id: "doc-module-params",
        segment_id: "seg-module-044",
        heading_path: "组件参数对照表 > 电流异常",
        excerpt: "组件局部遮挡、热斑和旁路二极管异常可能造成输出电流波动。",
        rerank_score: 0.58
      }
    ],
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 86 },
      { stage: "retrieve", label: "召回检索", milliseconds: 390 },
      { stage: "rerank", label: "重排", milliseconds: 230 },
      { stage: "generate", label: "生成回答", milliseconds: 614 },
      { stage: "total", label: "总耗时", milliseconds: 1320 }
    ],
    decision: { route: "rag", low_confidence: true },
    knowledgeGap: false,
    gapReason: null
  },
  {
    id: "log-high-latency-grid",
    question: "并网点电压波动大时先看哪些指标？",
    answerPreview: "建议先看并网点电压曲线、无功调节记录、逆变器限发状态和电能质量事件。",
    answerType: "rag",
    intent: "knowledge_base_qa",
    status: "answered",
    processStatus: "resolved",
    confidence: 0.81,
    traceId: "trace_qa_006",
    referenceCount: 3,
    latencyMs: 3260,
    createdAt: "2024-05-18 15:01:55",
    userName: "周工",
    references: [
      {
        rank: 1,
        document_id: "doc-quality-report",
        segment_id: "seg-quality-031",
        heading_path: "电能质量分析报告 > 电压波动",
        excerpt: "并网点电压波动需结合无功调节、限发策略和上级电网扰动分析。",
        rerank_score: 0.88
      },
      {
        rank: 2,
        document_id: "doc-station-design",
        segment_id: "seg-design-018",
        heading_path: "光伏电站设计规范 > 并网要求",
        excerpt: "并网点电压应满足当地电网技术规范，异常时需检查无功控制策略。",
        rerank_score: 0.8
      },
      {
        rank: 3,
        document_id: "doc-grid-failure",
        segment_id: "seg-grid-007",
        heading_path: "并网故障处理清单 > 电压异常",
        excerpt: "电压波动排查项包括 SVG 状态、逆变器功率因数设置和保护动作记录。",
        rerank_score: 0.72
      }
    ],
    stageLatencies: [
      { stage: "intent", label: "意图识别", milliseconds: 140 },
      { stage: "retrieve", label: "召回检索", milliseconds: 1040 },
      { stage: "rerank", label: "重排", milliseconds: 780 },
      { stage: "generate", label: "生成回答", milliseconds: 1300 },
      { stage: "total", label: "总耗时", milliseconds: 3260 }
    ],
    decision: { route: "rag", high_latency: true },
    knowledgeGap: false,
    gapReason: null
  }
];
