<script setup lang="ts">
import { Clock3, MessageSquareText, Plus, RefreshCw } from "@lucide/vue";
import { computed } from "vue";

import type { ChatConversation } from "../api/chat";

const props = defineProps<{
  conversations: ChatConversation[];
  selectedId: string;
  loading?: boolean;
  disabled?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  refresh: [];
  select: [conversationId: string];
  create: [];
}>();

const sortedConversations = computed(() =>
  [...props.conversations].sort((left, right) =>
    String(right.updatedAt || "").localeCompare(String(left.updatedAt || "")),
  ),
);

function displayTitle(conversation: ChatConversation): string {
  return conversation.title || `会话 ${conversation.conversationId.slice(0, 8)}`;
}

function formatTime(value?: string): string {
  if (!value) {
    return "未知时间";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
</script>

<template>
  <section class="conversation-panel" aria-label="最近会话">
    <header class="conversation-header">
      <div class="identity-icon">
        <MessageSquareText :size="18" aria-hidden="true" />
      </div>
      <div>
        <span>Conversations</span>
        <strong>最近会话</strong>
      </div>
      <div class="conversation-actions">
        <button
          class="icon-action"
          type="button"
          :disabled="loading || disabled"
          aria-label="刷新会话"
          @click="emit('refresh')"
        >
          <RefreshCw :class="{ spin: loading }" :size="16" aria-hidden="true" />
        </button>
        <button
          class="text-action"
          type="button"
          :disabled="disabled"
          @click="emit('create')"
        >
          <Plus :size="15" aria-hidden="true" />
          新会话
        </button>
      </div>
    </header>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="disabled" class="muted-line">登录并选择知识库后加载会话。</p>
    <p v-else-if="!loading && sortedConversations.length === 0" class="muted-line">
      当前知识库还没有会话。
    </p>

    <div v-else class="conversation-list">
      <button
        v-for="conversation in sortedConversations"
        :key="conversation.conversationId"
        class="conversation-item"
        :class="{ active: conversation.conversationId === selectedId }"
        type="button"
        @click="emit('select', conversation.conversationId)"
      >
        <span>{{ displayTitle(conversation) }}</span>
        <small>
          <Clock3 :size="13" aria-hidden="true" />
          {{ formatTime(conversation.updatedAt || conversation.createdAt) }}
        </small>
      </button>
    </div>
  </section>
</template>
