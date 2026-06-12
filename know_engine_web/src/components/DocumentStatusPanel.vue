<script setup lang="ts">
import {
  Activity,
  CheckCircle2,
  FileText,
  ListTree,
  RefreshCw,
  AlertTriangle,
} from "@lucide/vue";

import type {
  DocumentSplitResult,
  DocumentTask,
  KnowledgeDocument,
  KnowledgeSegment,
} from "../api/document";

const props = defineProps<{
  document: KnowledgeDocument | null;
  splitResult?: DocumentSplitResult | null;
  segments: KnowledgeSegment[];
  tasks: DocumentTask[];
  loading?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

function statusTone(status?: string): "ok" | "warning" | "error" | "muted" {
  if (!status) {
    return "muted";
  }
  const normalized = status.toLowerCase();
  if (["success", "vector_stored", "chunked", "converted"].includes(normalized)) {
    return "ok";
  }
  if (["failed", "error"].includes(normalized)) {
    return "error";
  }
  if (["uploaded", "running", "queued", "pending"].includes(normalized)) {
    return "warning";
  }
  return "muted";
}

function indexTaskTone(): "ok" | "warning" | "error" | "muted" {
  const task = latestIndexTask();
  if (task) {
    return statusTone(task.status);
  }
  if (props.splitResult?.indexQueued) {
    return "warning";
  }
  return "muted";
}

function indexTaskLabel(): string {
  const task = latestIndexTask();
  if (task) {
    return task.status;
  }
  if (props.splitResult?.indexQueued) {
    return "已投递";
  }
  return "未投递";
}

function latestIndexTask(): DocumentTask | undefined {
  return [...props.tasks]
    .reverse()
    .find((task) => task.taskType.toLowerCase() === "index");
}

function segmentKey(segment: KnowledgeSegment): number | string {
  return segment.id ?? segment.segment_id ?? segment.chunk_id ?? segment.chunk_order;
}
</script>

<template>
  <section class="document-status-panel">
    <header class="panel-heading-row">
      <div>
        <span>Processing Status</span>
        <h2>{{ document?.doc_title || "暂无文档" }}</h2>
      </div>
      <button
        class="icon-action"
        type="button"
        :disabled="!document || loading"
        aria-label="刷新文档状态"
        @click="emit('refresh')"
      >
        <RefreshCw :class="{ spin: loading }" :size="16" aria-hidden="true" />
      </button>
    </header>

    <div v-if="!document" class="document-empty">
      <FileText :size="26" aria-hidden="true" />
      <strong>上传一个文档后查看处理结果</strong>
      <span>这里会显示文档状态、切分数量、任务状态和片段预览。</span>
    </div>

    <template v-else>
      <div class="document-summary-grid">
        <div class="document-summary-card" :class="statusTone(document.status)">
          <FileText :size="18" aria-hidden="true" />
          <span>文档状态</span>
          <strong>{{ document.status }}</strong>
        </div>
        <div class="document-summary-card" :class="splitResult ? 'ok' : 'muted'">
          <ListTree :size="18" aria-hidden="true" />
          <span>切分数量</span>
          <strong>{{ splitResult?.segmentCount ?? segments.length }}</strong>
        </div>
        <div
          class="document-summary-card"
          :class="indexTaskTone()"
        >
          <Activity :size="18" aria-hidden="true" />
          <span>索引任务</span>
          <strong>{{ indexTaskLabel() }}</strong>
        </div>
      </div>

      <div v-if="document.conversionQueueError || splitResult?.indexQueueError" class="inline-alert warning">
        <AlertTriangle :size="16" aria-hidden="true" />
        <span>{{ document.conversionQueueError || splitResult?.indexQueueError }}</span>
      </div>

      <section class="status-block">
        <div class="section-heading">
          <Activity :size="17" aria-hidden="true" />
          <h3>任务状态</h3>
        </div>
        <div v-if="tasks.length" class="task-list">
          <div v-for="task in tasks" :key="task.taskId" class="task-row">
            <span class="status-pill" :class="statusTone(task.status)">
              {{ task.status }}
            </span>
            <strong>{{ task.taskType }}</strong>
            <small>{{ task.currentAttempt }} / {{ task.maxAttempts }}</small>
            <p v-if="task.lastError">{{ task.lastError }}</p>
          </div>
        </div>
        <p v-else class="muted-line">暂无任务记录</p>
      </section>

      <section class="status-block">
        <div class="section-heading">
          <ListTree :size="17" aria-hidden="true" />
          <h3>片段预览</h3>
        </div>
        <div v-if="segments.length" class="segment-list">
          <article
            v-for="segment in segments.slice(0, 5)"
            :key="segmentKey(segment)"
            class="segment-card"
          >
            <div>
              <CheckCircle2 :size="15" aria-hidden="true" />
              <strong>
                {{ segment.chunk_id || `segment-${segment.id ?? segment.segment_id}` }}
              </strong>
              <span>{{ segment.status }}</span>
            </div>
            <p>{{ segment.text }}</p>
          </article>
        </div>
        <p v-else class="muted-line">暂无切分片段</p>
      </section>
    </template>

    <p v-if="error" class="form-error">{{ error }}</p>
  </section>
</template>
