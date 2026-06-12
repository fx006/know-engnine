<script setup lang="ts">
import { Database, FileText, RefreshCw, Search } from "@lucide/vue";
import { computed, ref } from "vue";

import type { KnowledgeDocument } from "../api/document";
import {
  filterDocuments,
  statusFilterOptions,
  type DocumentStatusFilter,
} from "../utils/documents";

const props = defineProps<{
  documents: KnowledgeDocument[];
  selectedDocumentId?: number | null;
  loading?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [document: KnowledgeDocument];
}>();

const keyword = ref("");
const statusFilter = ref<DocumentStatusFilter>("all");

const filteredDocuments = computed(() =>
  filterDocuments(props.documents, {
    keyword: keyword.value,
    statusFilter: statusFilter.value,
  }),
);

const hasFilter = computed(
  () => keyword.value.trim().length > 0 || statusFilter.value !== "all",
);

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
</script>

<template>
  <section class="document-list-panel">
    <header class="panel-heading-row">
      <div>
        <span>Knowledge Documents</span>
        <h2>当前知识库文档</h2>
      </div>
      <button
        class="icon-action"
        type="button"
        :disabled="loading"
        aria-label="刷新文档列表"
        @click="emit('refresh')"
      >
        <RefreshCw :class="{ spin: loading }" :size="16" aria-hidden="true" />
      </button>
    </header>

    <div class="document-list-toolbar">
      <label class="document-search">
        <Search :size="16" aria-hidden="true" />
        <input
          v-model="keyword"
          type="search"
          placeholder="搜索标题、描述、状态"
          spellcheck="false"
        />
      </label>

      <div class="document-filter-row" aria-label="文档状态筛选">
        <button
          v-for="option in statusFilterOptions"
          :key="option.value"
          type="button"
          class="filter-chip"
          :class="{ active: option.value === statusFilter }"
          @click="statusFilter = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div v-if="filteredDocuments.length" class="document-list">
      <button
        v-for="document in filteredDocuments"
        :key="document.doc_id"
        class="document-list-item"
        :class="{ active: document.doc_id === selectedDocumentId }"
        type="button"
        @click="emit('select', document)"
      >
        <FileText :size="18" aria-hidden="true" />
        <span>
          <strong>{{ document.doc_title }}</strong>
          <small>{{ document.knowledge_base_type || "document" }}</small>
        </span>
        <em :class="statusTone(document.status)">{{ document.status }}</em>
      </button>
    </div>

    <div v-else class="document-list-empty">
      <Database :size="24" aria-hidden="true" />
      <strong>
        {{
          loading
            ? "正在加载文档"
            : hasFilter
              ? "没有匹配文档"
              : "暂无文档"
        }}
      </strong>
      <span>
        {{
          hasFilter
            ? "调整关键词或状态筛选后再试。"
            : "上传文档后，这里会按最近创建时间展示当前知识库文档。"
        }}
      </span>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
  </section>
</template>
