import { mockQaLogs } from "../mock/logs";
import type { QaLogItem } from "../types/log";

export async function listQaLogs(): Promise<QaLogItem[]> {
  return mockQaLogs.map((log) => ({
    ...log,
    references: log.references.map((reference) => ({ ...reference })),
    stageLatencies: log.stageLatencies.map((stage) => ({ ...stage })),
    decision: { ...log.decision }
  }));
}

export async function markQaLogProcessed(log: QaLogItem): Promise<QaLogItem> {
  return { ...log, processStatus: "resolved" };
}

export async function createUnansweredFromLog(log: QaLogItem): Promise<QaLogItem> {
  return { ...log, processStatus: "reviewed", knowledgeGap: true };
}
