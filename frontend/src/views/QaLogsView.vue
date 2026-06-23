<script setup lang="ts">
import { computed } from "vue";
import {
  CircleCheck,
  Clock,
  Collection,
  CopyDocument,
  DataAnalysis,
  Search,
  Warning
} from "@element-plus/icons-vue";

import { useQaLogStore } from "../stores/logs";
import type { QaLogAnswerType, QaLogItem, QaLogProcessStatus, QaLogStatus } from "../types/log";

const logStore = useQaLogStore();

const metricCards = computed(() => [
  { label: "全部记录", value: logStore.summary.total, icon: Collection, tone: "blue" },
  { label: "已回答", value: logStore.summary.answered, icon: CircleCheck, tone: "green" },
  { label: "证据不足", value: logStore.summary.insufficientEvidence, icon: Warning, tone: "amber" },
  { label: "拒答", value: logStore.summary.refused, icon: Warning, tone: "red" },
  { label: "低置信度", value: logStore.summary.lowConfidence, icon: DataAnalysis, tone: "purple" },
  { label: "高耗时", value: logStore.summary.highLatency, icon: Clock, tone: "cyan" }
]);

const answerTypeTabs: Array<{ label: string; value: QaLogAnswerType | "all" }> = [
  { label: "全部", value: "all" },
  { label: "知识库回答", value: "rag" },
  { label: "通用解释", value: "general_llm" },
  { label: "拒答", value: "refused" },
  { label: "证据不足", value: "none" }
];

function answerTypeLabel(answerType: QaLogAnswerType) {
  const labels: Record<QaLogAnswerType, string> = {
    rag: "知识库回答",
    general_llm: "通用解释",
    refused: "拒答",
    none: "证据不足"
  };
  return labels[answerType];
}

function statusLabel(status: QaLogStatus) {
  const labels: Record<QaLogStatus, string> = {
    answered: "已回答",
    insufficient_evidence: "证据不足",
    refused: "拒答",
    low_confidence: "低置信度",
    error: "接口错误"
  };
  return labels[status];
}

function processLabel(status: QaLogProcessStatus) {
  const labels: Record<QaLogProcessStatus, string> = {
    new: "待处理",
    reviewed: "已查看",
    resolved: "已处理"
  };
  return labels[status];
}

function formatConfidence(confidence: number | null) {
  return confidence === null ? "-" : `${Math.round(confidence * 100)}%`;
}

function formatLatency(milliseconds: number) {
  return `${milliseconds} ms`;
}

function selectLog(log: QaLogItem) {
  logStore.selectLog(log.id);
}
</script>

<template>
  <section class="qa-log-page">
    <main class="qa-log-main">
      <header class="qa-log-hero">
        <div>
          <p class="eyebrow">Trace Console</p>
          <h1>问答日志</h1>
          <span>追踪回答类型、证据状态、trace_id、引用片段与阶段耗时</span>
        </div>
        <strong>当前为 mock 查询链路，真实日志接口待后端接入</strong>
      </header>

      <section class="qa-log-metrics" aria-label="问答日志统计">
        <article v-for="metric in metricCards" :key="metric.label" class="qa-log-metric-card" :class="metric.tone">
          <span>
            <component :is="metric.icon" aria-hidden="true" />
          </span>
          <div>
            <p>{{ metric.label }}</p>
            <strong>{{ metric.value }}</strong>
          </div>
        </article>
      </section>

      <section class="qa-log-tabs" aria-label="回答类型筛选">
        <button
          v-for="tab in answerTypeTabs"
          :key="tab.value"
          type="button"
          :class="{ active: logStore.filters.answerType === tab.value }"
          @click="logStore.setAnswerType(tab.value)"
        >
          {{ tab.label }}
        </button>
      </section>

      <section class="qa-log-filter-bar" aria-label="日志筛选">
        <label class="qa-log-search">
          <Search aria-hidden="true" />
          <input
            :value="logStore.filters.keyword"
            type="search"
            placeholder="搜索问题、回答摘要或 trace_id"
            @input="logStore.setKeyword(($event.target as HTMLInputElement).value)"
          />
        </label>

        <select
          :value="logStore.filters.status"
          aria-label="回答状态"
          @change="logStore.setStatus(($event.target as HTMLSelectElement).value as QaLogStatus | 'all')"
        >
          <option v-for="option in logStore.statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <select
          :value="logStore.filters.processStatus"
          aria-label="处理状态"
          @change="logStore.setProcessStatus(($event.target as HTMLSelectElement).value as QaLogProcessStatus | 'all')"
        >
          <option v-for="option in logStore.processStatusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <button class="qa-log-reset" type="button" @click="logStore.resetFilters">重置</button>
      </section>

      <section class="qa-log-table-card">
        <table class="qa-log-table">
          <thead>
            <tr>
              <th>问题</th>
              <th>回答类型</th>
              <th>状态</th>
              <th>置信度</th>
              <th>trace_id</th>
              <th>引用</th>
              <th>耗时</th>
              <th>时间</th>
              <th>处理状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logStore.paginatedLogs" :key="log.id" @click="selectLog(log)">
              <td>
                <strong>{{ log.question }}</strong>
                <p>{{ log.answerPreview }}</p>
              </td>
              <td>
                <span class="qa-log-answer-tag" :class="log.answerType">{{ answerTypeLabel(log.answerType) }}</span>
              </td>
              <td>
                <span class="qa-log-status-tag" :class="log.status">{{ statusLabel(log.status) }}</span>
              </td>
              <td>{{ formatConfidence(log.confidence) }}</td>
              <td>
                <button class="qa-log-trace" type="button" @click.stop="logStore.copyTraceId(log.traceId)">
                  {{ log.traceId }}
                </button>
              </td>
              <td>{{ log.referenceCount }}</td>
              <td>{{ formatLatency(log.latencyMs) }}</td>
              <td>{{ log.createdAt }}</td>
              <td>
                <span class="qa-log-process-tag" :class="log.processStatus">
                  {{ processLabel(log.processStatus) }}
                </span>
              </td>
              <td>
                <button class="qa-log-detail-button" type="button" @click.stop="selectLog(log)">查看详情</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="logStore.paginatedLogs.length === 0" class="qa-log-empty">
          当前筛选条件下没有日志，试试重置筛选。
        </div>
      </section>

      <footer class="qa-log-pagination">
        <span>共 {{ logStore.filteredLogs.length }} 条</span>
        <div>
          <button type="button" :disabled="logStore.filters.page <= 1" @click="logStore.setPage(logStore.filters.page - 1)">
            上一页
          </button>
          <button
            v-for="page in logStore.totalPages"
            :key="page"
            type="button"
            :class="{ active: page === logStore.filters.page }"
            @click="logStore.setPage(page)"
          >
            {{ page }}
          </button>
          <button
            type="button"
            :disabled="logStore.filters.page >= logStore.totalPages"
            @click="logStore.setPage(logStore.filters.page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>

      <p v-if="logStore.copyMessage" class="qa-log-notice">{{ logStore.copyMessage }}</p>
    </main>

    <aside class="qa-log-drawer" :class="{ open: logStore.selectedLog }" aria-label="日志详情">
      <template v-if="logStore.selectedLog">
        <header>
          <div>
            <p>Trace Detail</p>
            <h2>日志详情</h2>
          </div>
          <button type="button" aria-label="关闭详情" @click="logStore.closeDetail">×</button>
        </header>

        <section class="qa-log-detail-block">
          <span>问题</span>
          <strong>{{ logStore.selectedLog.question }}</strong>
          <p>{{ logStore.selectedLog.answerPreview }}</p>
        </section>

        <section class="qa-log-detail-grid">
          <div>
            <span>trace_id</span>
            <button type="button" @click="logStore.copyTraceId(logStore.selectedLog.traceId)">
              <CopyDocument aria-hidden="true" />
              {{ logStore.selectedLog.traceId }}
            </button>
          </div>
          <div>
            <span>回答类型</span>
            <strong>{{ answerTypeLabel(logStore.selectedLog.answerType) }}</strong>
          </div>
          <div>
            <span>意图</span>
            <strong>{{ logStore.selectedLog.intent }}</strong>
          </div>
          <div>
            <span>置信度</span>
            <strong>{{ formatConfidence(logStore.selectedLog.confidence) }}</strong>
          </div>
        </section>

        <section class="qa-log-detail-block">
          <span>引用片段</span>
          <article v-for="reference in logStore.selectedLog.references" :key="reference.segment_id ?? reference.rank">
            <strong>{{ reference.rank }}. {{ reference.heading_path }}</strong>
            <p>{{ reference.excerpt }}</p>
            <em>rerank_score: {{ reference.rerank_score ?? "-" }}</em>
          </article>
          <p v-if="logStore.selectedLog.references.length === 0">本次未使用知识库引用。</p>
        </section>

        <section class="qa-log-detail-block">
          <span>阶段耗时</span>
          <div v-for="stage in logStore.selectedLog.stageLatencies" :key="stage.stage" class="qa-log-stage-row">
            <strong>{{ stage.label }}</strong>
            <i>
              <b :style="{ width: `${Math.min(100, (stage.milliseconds / logStore.selectedLog.latencyMs) * 100)}%` }" />
            </i>
            <em>{{ stage.milliseconds }} ms</em>
          </div>
        </section>

        <section class="qa-log-detail-block">
          <span>知识缺口判断</span>
          <strong>{{ logStore.selectedLog.knowledgeGap ? "存在知识缺口" : "暂无明显知识缺口" }}</strong>
          <p>{{ logStore.selectedLog.gapReason ?? "当前日志不需要进入未命中问题回流。" }}</p>
        </section>

        <footer>
          <button type="button" @click="logStore.markProcessed(logStore.selectedLog.id)">标记已处理</button>
          <button type="button" class="primary" @click="logStore.createUnansweredFromLog(logStore.selectedLog.id)">
            加入未命中问题
          </button>
        </footer>
      </template>
    </aside>
  </section>
</template>
