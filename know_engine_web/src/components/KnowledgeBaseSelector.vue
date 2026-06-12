<script setup lang="ts">
import { BookOpen, Database, RefreshCw } from "@lucide/vue";
import { computed } from "vue";

import type { KnowledgeBase } from "../api/knowledgeBase";

const props = defineProps<{
  knowledgeBases: KnowledgeBase[];
  selectedId: string;
  loading?: boolean;
  disabled?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [knowledgeBaseId: string];
}>();

const selectedKnowledgeBase = computed(
  () =>
    props.knowledgeBases.find(
      (knowledgeBase) => knowledgeBase.knowledgeBaseId === props.selectedId,
    ) || null,
);

function selectKnowledgeBase(value: string | number | boolean) {
  emit("select", String(value));
}
</script>

<template>
  <section class="kb-panel" aria-label="知识库选择">
    <header class="kb-header">
      <div class="identity-icon">
        <Database :size="18" aria-hidden="true" />
      </div>
      <div>
        <span>Knowledge Base</span>
        <strong>{{ selectedKnowledgeBase?.name || "请选择知识库" }}</strong>
      </div>
      <button
        class="icon-action"
        type="button"
        :disabled="loading || disabled"
        aria-label="刷新知识库列表"
        @click="emit('refresh')"
      >
        <RefreshCw :class="{ spin: loading }" :size="16" aria-hidden="true" />
      </button>
    </header>

    <el-select
      class="kb-select"
      :model-value="selectedId"
      :disabled="disabled || loading || knowledgeBases.length === 0"
      placeholder="选择知识库"
      size="large"
      @update:model-value="selectKnowledgeBase"
    >
      <el-option
        v-for="knowledgeBase in knowledgeBases"
        :key="knowledgeBase.knowledgeBaseId"
        :label="knowledgeBase.name"
        :value="knowledgeBase.knowledgeBaseId"
      >
        <div class="kb-option">
          <span>{{ knowledgeBase.name }}</span>
          <small>{{ knowledgeBase.visibility }} / {{ knowledgeBase.status }}</small>
        </div>
      </el-option>
    </el-select>

    <div v-if="selectedKnowledgeBase" class="kb-detail">
      <BookOpen :size="15" aria-hidden="true" />
      <span>{{ selectedKnowledgeBase.description || selectedKnowledgeBase.groupId }}</span>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!disabled && !loading && knowledgeBases.length === 0" class="muted-line">
      当前用户还没有可访问的知识库。
    </p>
  </section>
</template>
