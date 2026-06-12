<script setup lang="ts">
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Bot,
  Car,
  Database,
  FileText,
  Loader2,
  MessageSquareText,
  Send,
  Server,
  Settings2,
} from "@lucide/vue";
import { ElMessage } from "element-plus";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import { getCurrentUser, login, type AuthUser } from "./api/auth";
import {
  listChatConversations,
  listChatMessages,
  streamChat,
  type ChatConversation,
} from "./api/chat";
import {
  listDocuments,
  listDocumentSegments,
  listDocumentTasks,
  type DocumentSplitResult,
  type DocumentTask,
  type KnowledgeDocument,
  type KnowledgeSegment,
} from "./api/document";
import { checkApiHealth, type HealthStatus } from "./api/health";
import {
  listKnowledgeBases,
  type KnowledgeBase,
} from "./api/knowledgeBase";
import type { SseErrorPayload, SseEvent } from "./api/sse";
import AdminHealthPanel from "./components/AdminHealthPanel.vue";
import ConversationListPanel from "./components/ConversationListPanel.vue";
import DocumentListPanel from "./components/DocumentListPanel.vue";
import DocumentStatusPanel from "./components/DocumentStatusPanel.vue";
import DocumentUploadPanel from "./components/DocumentUploadPanel.vue";
import KnowledgeBaseSelector from "./components/KnowledgeBaseSelector.vue";
import LoginPanel from "./components/LoginPanel.vue";
import SqlResultCard from "./components/SqlResultCard.vue";
import type {
  ChatMessage,
  ClarificationChoice,
  RagReference,
  StreamTraceItem,
} from "./types/chat";
import { splitReferencesBySource } from "./utils/references";

type ActiveView = "client-chat" | "client-documents" | "admin-health";

const AUTH_STORAGE_KEY = "know_engine_auth";
const KB_STORAGE_KEY = "know_engine_selected_kb";
const CONVERSATION_STORAGE_KEY = "know_engine_selected_conversation";

const apiBaseUrl = ref(import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000");
const accessToken = ref("");
const refreshToken = ref("");
const currentUser = ref<AuthUser | null>(null);
const authLoading = ref(false);
const authError = ref("");
const knowledgeBases = ref<KnowledgeBase[]>([]);
const knowledgeBaseId = ref("");
const kbLoading = ref(false);
const kbError = ref("");
const conversationId = ref("");
const conversations = ref<ChatConversation[]>([]);
const conversationLoading = ref(false);
const conversationError = ref("");
const messageHistoryLoading = ref(false);
const question = ref("我的车保养多少钱？");
const sending = ref(false);
const backendStatus = ref<HealthStatus>("offline");
const checkingHealth = ref(false);
const activeView = ref<ActiveView>("client-chat");
const messages = ref<ChatMessage[]>([]);
const traceItems = ref<StreamTraceItem[]>([]);
const chatBodyRef = ref<HTMLElement | null>(null);
const currentDocument = ref<KnowledgeDocument | null>(null);
const currentSplitResult = ref<DocumentSplitResult | null>(null);
const documents = ref<KnowledgeDocument[]>([]);
const documentListLoading = ref(false);
const documentListError = ref("");
const documentSegments = ref<KnowledgeSegment[]>([]);
const documentTasks = ref<DocumentTask[]>([]);
const documentStatusLoading = ref(false);
const documentStatusError = ref("");
let abortController: AbortController | null = null;
let documentPollingTimer: ReturnType<typeof window.setInterval> | null = null;

const lastAssistant = computed(() =>
  [...messages.value].reverse().find((message) => message.role === "assistant"),
);

const referenceCount = computed(
  () => messages.value.flatMap((message) => message.references || []).length,
);

const assistantReferences = computed(() =>
  splitReferencesBySource(lastAssistant.value?.references),
);

const warningCount = computed(
  () => messages.value.flatMap((message) => message.warnings || []).length,
);

const selectedKnowledgeBase = computed(
  () =>
    knowledgeBases.value.find(
      (knowledgeBase) => knowledgeBase.knowledgeBaseId === knowledgeBaseId.value,
    ) || null,
);

const scopedConversations = computed(() =>
  conversations.value.filter(
    (conversation) =>
      !knowledgeBaseId.value ||
      !conversation.knowledgeBaseId ||
      conversation.knowledgeBaseId === knowledgeBaseId.value,
  ),
);

const pageTitle = computed(() => {
  if (activeView.value === "client-chat") {
    return "对话工作台";
  }
  if (activeView.value === "client-documents") {
    return "文档工作台";
  }
  return "管理控制台";
});

const pageDescription = computed(() => {
  if (activeView.value === "client-chat") {
    return "Knowledge scoped chat with streaming trace";
  }
  if (activeView.value === "client-documents") {
    return "Import, split, and inspect documents in the selected knowledge base";
  }
  return "Runtime health and operational readiness";
});

const quickQuestions = [
  "我的车保养多少钱？",
  "官方客服电话是多少？",
  "售后投诉处理规则是什么？",
  "Model Y 长续航版指导价是多少？",
];

onMounted(() => {
  void refreshHealth();
  void restoreAuthSession();
});

onUnmounted(() => {
  stopDocumentPolling();
});

watch([activeView, knowledgeBaseId, accessToken], () => {
  if (activeView.value !== "client-documents") {
    stopDocumentPolling();
    return;
  }
  void loadDocuments();
  syncDocumentPolling();
});

watch(currentDocument, () => {
  syncDocumentPolling();
});

async function refreshHealth() {
  checkingHealth.value = true;
  backendStatus.value = await checkApiHealth(apiBaseUrl.value);
  checkingHealth.value = false;
}

async function restoreAuthSession() {
  const storedAuth = readStoredAuth();
  if (!storedAuth?.accessToken) {
    return;
  }

  accessToken.value = storedAuth.accessToken;
  refreshToken.value = storedAuth.refreshToken || "";
  authLoading.value = true;
  authError.value = "";

  try {
    currentUser.value = await getCurrentUser({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
    });
    await loadKnowledgeBases({
      preferredKnowledgeBaseId: localStorage.getItem(KB_STORAGE_KEY) || "",
    });
    await loadConversations({
      preferredConversationId: localStorage.getItem(CONVERSATION_STORAGE_KEY) || "",
    });
  } catch (error) {
    clearAuthSession();
    authError.value = toClientErrorMessage(error);
  } finally {
    authLoading.value = false;
  }
}

async function loginUser(payload: { username: string; password: string }) {
  if (authLoading.value) {
    return;
  }

  authLoading.value = true;
  authError.value = "";
  kbError.value = "";

  try {
    const tokenPair = await login({
      baseUrl: apiBaseUrl.value,
      username: payload.username,
      password: payload.password,
    });

    accessToken.value = tokenPair.accessToken;
    refreshToken.value = tokenPair.refreshToken;
    currentUser.value = tokenPair.user;
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        accessToken: tokenPair.accessToken,
        refreshToken: tokenPair.refreshToken,
      }),
    );
    await loadKnowledgeBases();
    await loadConversations();
    ElMessage.success("登录成功，已加载可访问知识库");
  } catch (error) {
    clearAuthSession();
    authError.value = toClientErrorMessage(error);
  } finally {
    authLoading.value = false;
  }
}

function logoutUser() {
  clearAuthSession();
  messages.value = [];
  traceItems.value = [];
  ElMessage.success("已退出登录");
}

async function loadKnowledgeBases(options?: { preferredKnowledgeBaseId?: string }) {
  if (!accessToken.value) {
    knowledgeBases.value = [];
    knowledgeBaseId.value = "";
    return;
  }

  kbLoading.value = true;
  kbError.value = "";

  try {
    knowledgeBases.value = await listKnowledgeBases({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
    });
    const preferredKnowledgeBaseId =
      options?.preferredKnowledgeBaseId || knowledgeBaseId.value;
    const nextKnowledgeBase =
      knowledgeBases.value.find(
        (knowledgeBase) =>
          knowledgeBase.knowledgeBaseId === preferredKnowledgeBaseId,
      ) || knowledgeBases.value[0];
    selectKnowledgeBase(nextKnowledgeBase?.knowledgeBaseId || "", {
      resetConversation: false,
    });
  } catch (error) {
    kbError.value = toClientErrorMessage(error);
  } finally {
    kbLoading.value = false;
  }
}

function selectKnowledgeBase(
  nextKnowledgeBaseId: string,
  options?: { resetConversation?: boolean },
) {
  if (knowledgeBaseId.value === nextKnowledgeBaseId) {
    return;
  }

  knowledgeBaseId.value = nextKnowledgeBaseId;
  if (nextKnowledgeBaseId) {
    localStorage.setItem(KB_STORAGE_KEY, nextKnowledgeBaseId);
  } else {
    localStorage.removeItem(KB_STORAGE_KEY);
  }

  if (options?.resetConversation ?? true) {
    startNewConversation();
    clearDocumentState();
  }
}

function clearAuthSession() {
  accessToken.value = "";
  refreshToken.value = "";
  currentUser.value = null;
  knowledgeBases.value = [];
  knowledgeBaseId.value = "";
  conversationId.value = "";
  conversations.value = [];
  conversationError.value = "";
  clearDocumentState();
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(KB_STORAGE_KEY);
  localStorage.removeItem(CONVERSATION_STORAGE_KEY);
}

async function loadConversations(options?: {
  preferredConversationId?: string;
  silent?: boolean;
}) {
  if (!accessToken.value) {
    conversations.value = [];
    return;
  }

  if (!options?.silent) {
    conversationLoading.value = true;
  }
  conversationError.value = "";

  try {
    conversations.value = await listChatConversations({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
    });

    const preferredConversationId =
      options?.preferredConversationId || conversationId.value;
    const preferredConversation = conversations.value.find(
      (conversation) =>
        conversation.conversationId === preferredConversationId &&
        (!knowledgeBaseId.value ||
          !conversation.knowledgeBaseId ||
          conversation.knowledgeBaseId === knowledgeBaseId.value),
    );

    if (preferredConversation && messages.value.length === 0) {
      await selectConversation(preferredConversation.conversationId);
    }
  } catch (error) {
    conversationError.value = toClientErrorMessage(error);
  } finally {
    if (!options?.silent) {
      conversationLoading.value = false;
    }
  }
}

async function selectConversation(nextConversationId: string) {
  if (!nextConversationId) {
    return;
  }

  const conversation = conversations.value.find(
    (item) => item.conversationId === nextConversationId,
  );
  if (conversation?.knowledgeBaseId && conversation.knowledgeBaseId !== knowledgeBaseId.value) {
    selectKnowledgeBase(conversation.knowledgeBaseId, { resetConversation: false });
  }

  conversationId.value = nextConversationId;
  localStorage.setItem(CONVERSATION_STORAGE_KEY, nextConversationId);
  traceItems.value = [];
  messageHistoryLoading.value = true;
  conversationError.value = "";

  try {
    messages.value = await listChatMessages({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
      conversationId: nextConversationId,
    });
    await scrollToBottom();
  } catch (error) {
    conversationError.value = toClientErrorMessage(error);
  } finally {
    messageHistoryLoading.value = false;
  }
}

function startNewConversation() {
  conversationId.value = "";
  messages.value = [];
  traceItems.value = [];
  localStorage.removeItem(CONVERSATION_STORAGE_KEY);
}

function clearDocumentState() {
  currentDocument.value = null;
  currentSplitResult.value = null;
  documents.value = [];
  documentListError.value = "";
  documentSegments.value = [];
  documentTasks.value = [];
  documentStatusError.value = "";
  stopDocumentPolling();
}

async function handleDocumentImported(payload: {
  document: KnowledgeDocument;
  split?: DocumentSplitResult;
}) {
  currentDocument.value = payload.document;
  currentSplitResult.value = payload.split || null;
  upsertDocument(payload.document);
  await loadDocuments({ preserveSelection: true });
  await refreshDocumentStatus();

  if (payload.split) {
    ElMessage.success(`导入并切分完成，共 ${payload.split.segmentCount} 个片段`);
    return;
  }

  ElMessage.success("文档已上传，等待转换任务处理");
}

async function loadDocuments(options?: { preserveSelection?: boolean }) {
  if (!accessToken.value || !knowledgeBaseId.value) {
    documents.value = [];
    return;
  }

  documentListLoading.value = true;
  documentListError.value = "";

  try {
    const loadedDocuments = await listDocuments({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
      knowledgeBaseId: knowledgeBaseId.value,
    });
    documents.value = loadedDocuments;

    if (!options?.preserveSelection) {
      currentDocument.value = loadedDocuments[0] || null;
      currentSplitResult.value = null;
    } else if (currentDocument.value) {
      const latestSelected = loadedDocuments.find(
        (document) => document.doc_id === currentDocument.value?.doc_id,
      );
      if (latestSelected) {
        currentDocument.value = latestSelected;
      }
    }

    if (currentDocument.value) {
      await refreshDocumentStatus({ silent: true });
    }
  } catch (error) {
    documentListError.value = toClientErrorMessage(error);
  } finally {
    documentListLoading.value = false;
  }
}

async function selectDocument(document: KnowledgeDocument) {
  currentDocument.value = document;
  currentSplitResult.value = null;
  await refreshDocumentStatus();
}

function upsertDocument(document: KnowledgeDocument) {
  const rest = documents.value.filter((item) => item.doc_id !== document.doc_id);
  documents.value = [document, ...rest];
}

async function refreshDocumentStatus(options?: { silent?: boolean }) {
  if (!currentDocument.value) {
    return;
  }

  if (!options?.silent) {
    documentStatusLoading.value = true;
  }
  documentStatusError.value = "";

  try {
    const [segments, tasks] = await Promise.all([
      listDocumentSegments({
        baseUrl: apiBaseUrl.value,
        documentId: currentDocument.value.doc_id,
      }),
      listDocumentTasks({
        baseUrl: apiBaseUrl.value,
        accessToken: accessToken.value,
        documentId: currentDocument.value.doc_id,
      }),
    ]);
    documentSegments.value = segments;
    documentTasks.value = tasks;
  } catch (error) {
    documentStatusError.value = toClientErrorMessage(error);
  } finally {
    if (!options?.silent) {
      documentStatusLoading.value = false;
    }
  }
}

function syncDocumentPolling() {
  stopDocumentPolling();
  if (
    activeView.value !== "client-documents" ||
    !currentDocument.value ||
    !accessToken.value
  ) {
    return;
  }

  documentPollingTimer = window.setInterval(() => {
    void refreshDocumentStatus({ silent: true });
  }, 6000);
}

function stopDocumentPolling() {
  if (documentPollingTimer !== null) {
    window.clearInterval(documentPollingTimer);
    documentPollingTimer = null;
  }
}

function readStoredAuth(): { accessToken: string; refreshToken?: string } | null {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as { accessToken: string; refreshToken?: string };
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

async function sendQuestion() {
  const content = question.value.trim();
  if (!content || sending.value) {
    return;
  }

  if (!currentUser.value) {
    ElMessage.warning("请先登录，再开始对话");
    return;
  }

  if (!knowledgeBaseId.value) {
    ElMessage.warning("请先选择知识库");
    return;
  }

  const assistant: ChatMessage = {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    pending: true,
    references: [],
    warnings: [],
  };

  messages.value.push({
    id: crypto.randomUUID(),
    role: "user",
    content,
  });
  messages.value.push(assistant);
  traceItems.value = [];
  sending.value = true;
  abortController = new AbortController();
  question.value = "";
  await scrollToBottom();

  try {
    await streamChat({
      baseUrl: apiBaseUrl.value,
      userId: currentUser.value.userId,
      knowledgeBaseId: knowledgeBaseId.value,
      accessToken: accessToken.value || undefined,
      conversationId: conversationId.value || undefined,
      content,
      signal: abortController.signal,
      onEvent: (event) => handleStreamEvent(event, assistant),
      onComplete: (completedConversationId) =>
        refreshCompletedConversationMessages(completedConversationId),
    });
  } catch (error) {
    assistant.error = {
      code: "CLIENT_STREAM_ERROR",
      message: toClientErrorMessage(error),
    };
    await refreshHealth();
  } finally {
    assistant.pending = false;
    sending.value = false;
    abortController = null;
    await scrollToBottom();
  }
}

function notifyComingSoon(moduleName: string) {
  ElMessage.info(`${moduleName} 页面会在 Day18 后续任务接入`);
}

function switchView(view: ActiveView) {
  activeView.value = view;
}

function updateBackendStatus(status: HealthStatus) {
  backendStatus.value = status;
}

function stopStreaming() {
  abortController?.abort();
}

function useQuickQuestion(value: string) {
  question.value = value;
}

function toClientErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || "");
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "无法连接后端服务，请先启动 FastAPI，或检查 API 地址和跨域配置";
  }
  return message || "聊天请求失败";
}

function handleStreamEvent(event: SseEvent, assistant: ChatMessage) {
  if (event.kind === "progress") {
    traceItems.value.push({
      id: crypto.randomUUID(),
      kind: "progress",
      text: event.payload,
    });
  }

  if (event.kind === "answer_delta") {
    assistant.content += event.payload;
  }

  if (event.kind === "reference") {
    assistant.references = (event.data as RagReference[]) || [];
  }

  if (event.kind === "card") {
    assistant.cardMessage = event.payload;
  }

  if (event.kind === "card_choice") {
    assistant.cardChoices = (event.data as ClarificationChoice[]) || [];
  }

  if (event.kind === "warning") {
    assistant.warnings = [...(assistant.warnings || []), event.payload];
  }

  if (event.kind === "error") {
    assistant.error = event.data as SseErrorPayload;
  }

  if (event.kind === "done" && event.conversationId) {
    conversationId.value = event.conversationId;
    localStorage.setItem(CONVERSATION_STORAGE_KEY, event.conversationId);
    void loadConversations({ silent: true });
    traceItems.value.push({
      id: crypto.randomUUID(),
      kind: "done",
      text: `会话 ${event.conversationId}`,
    });
  }

  void scrollToBottom();
}

async function refreshCompletedConversationMessages(completedConversationId: string) {
  if (!accessToken.value || !completedConversationId) {
    return;
  }

  try {
    const persistedMessages = await listChatMessages({
      baseUrl: apiBaseUrl.value,
      accessToken: accessToken.value,
      conversationId: completedConversationId,
    });

    if (conversationId.value === completedConversationId) {
      messages.value = persistedMessages;
      await scrollToBottom();
    }
  } catch (error) {
    conversationError.value = toClientErrorMessage(error);
  }
}

async function scrollToBottom() {
  await nextTick();
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight;
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">
          <Bot :size="22" aria-hidden="true" />
        </div>
        <div>
          <div class="brand-name">Know Engine</div>
          <div class="brand-meta">RAG Console</div>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <div class="nav-group-label">客户端</div>
        <button
          class="nav-item"
          :class="{ active: activeView === 'client-chat' }"
          type="button"
          @click="switchView('client-chat')"
        >
          <MessageSquareText :size="18" aria-hidden="true" />
          <span>对话工作台</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'client-documents' }"
          type="button"
          @click="switchView('client-documents')"
        >
          <FileText :size="18" aria-hidden="true" />
          <span>文档工作台</span>
        </button>
        <div class="nav-group-label">管理端</div>
        <button
          class="nav-item"
          :class="{ active: activeView === 'admin-health' }"
          type="button"
          @click="switchView('admin-health')"
        >
          <Server :size="18" aria-hidden="true" />
          <span>环境健康</span>
        </button>
        <button class="nav-item" type="button" @click="notifyComingSoon('知识库')">
          <Database :size="18" aria-hidden="true" />
          <span>知识库</span>
          <small>Soon</small>
        </button>
        <button class="nav-item" type="button" @click="notifyComingSoon('任务')">
          <Activity :size="18" aria-hidden="true" />
          <span>任务</span>
          <small>Soon</small>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="mini-stat">
          <span>References</span>
          <strong>{{ referenceCount }}</strong>
        </div>
        <div class="mini-stat">
          <span>Warnings</span>
          <strong>{{ warningCount }}</strong>
        </div>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageDescription }}</p>
        </div>
        <button
          class="runtime-chip"
          :class="{
            live: sending,
            degraded: backendStatus === 'degraded',
            offline: backendStatus === 'offline',
          }"
          type="button"
          @click="refreshHealth"
        >
          <Loader2 v-if="sending" class="spin" :size="16" aria-hidden="true" />
          <Loader2
            v-else-if="checkingHealth"
            class="spin"
            :size="16"
            aria-hidden="true"
          />
          <Server v-else :size="16" aria-hidden="true" />
          <span>
            {{
              sending
                ? "Streaming"
                : backendStatus === "online"
                  ? "Backend online"
                  : backendStatus === "degraded"
                    ? "Backend degraded"
                    : "Backend offline"
            }}
          </span>
        </button>
      </header>

      <section
        class="config-bar"
        :class="{ compact: true }"
        aria-label="运行配置"
      >
        <label>
          <span>API</span>
          <el-input v-model="apiBaseUrl" size="large" spellcheck="false" />
        </label>
      </section>

      <section v-if="activeView !== 'admin-health'" class="context-grid">
        <LoginPanel
          :user="currentUser"
          :loading="authLoading"
          :error="authError"
          @login="loginUser"
          @logout="logoutUser"
        />
        <KnowledgeBaseSelector
          :knowledge-bases="knowledgeBases"
          :selected-id="knowledgeBaseId"
          :loading="kbLoading"
          :disabled="!currentUser"
          :error="kbError"
          @refresh="loadKnowledgeBases"
          @select="(value) => selectKnowledgeBase(value)"
        />
        <ConversationListPanel
          :conversations="scopedConversations"
          :selected-id="conversationId"
          :loading="conversationLoading || messageHistoryLoading"
          :disabled="!currentUser || !knowledgeBaseId"
          :error="conversationError"
          @refresh="loadConversations"
          @create="startNewConversation"
          @select="selectConversation"
        />
      </section>

      <AdminHealthPanel
        v-if="activeView === 'admin-health'"
        :api-base-url="apiBaseUrl"
        @status-change="updateBackendStatus"
      />

      <section v-else-if="activeView === 'client-documents'" class="document-workspace">
        <div class="document-side-stack">
          <DocumentUploadPanel
            :api-base-url="apiBaseUrl"
            :access-token="accessToken"
            :knowledge-base-id="knowledgeBaseId"
            :disabled="!currentUser || !knowledgeBaseId"
            @imported="handleDocumentImported"
          />
          <DocumentListPanel
            :documents="documents"
            :selected-document-id="currentDocument?.doc_id"
            :loading="documentListLoading"
            :error="documentListError"
            @refresh="loadDocuments"
            @select="selectDocument"
          />
        </div>
        <DocumentStatusPanel
          :document="currentDocument"
          :split-result="currentSplitResult"
          :segments="documentSegments"
          :tasks="documentTasks"
          :loading="documentStatusLoading"
          :error="documentStatusError"
          @refresh="refreshDocumentStatus"
        />
      </section>

      <section v-else class="content-grid">
        <div class="chat-panel">
          <div ref="chatBodyRef" class="chat-body">
            <div
              v-if="messageHistoryLoading && messages.length === 0"
              class="empty-state"
            >
              <Loader2 class="spin" :size="26" aria-hidden="true" />
              <strong>正在加载会话历史</strong>
            </div>

            <div v-else-if="messages.length === 0" class="empty-state">
              <BookOpen :size="26" aria-hidden="true" />
              <strong>选择一个问题开始</strong>
            </div>

            <article
              v-for="message in messages"
              :key="message.id"
              class="message-row"
              :class="message.role"
            >
              <div class="message-bubble">
                <div class="message-role">
                  {{ message.role === "user" ? "You" : "Assistant" }}
                </div>
                <p v-if="message.content">{{ message.content }}</p>
                <p v-else-if="message.pending" class="muted-line">等待响应...</p>

                <div v-if="message.cardMessage" class="clarify-block">
                  <div class="clarify-title">
                    <Car :size="16" aria-hidden="true" />
                    <span>{{ message.cardMessage }}</span>
                  </div>
                  <div class="choice-list">
                    <button
                      v-for="choice in message.cardChoices"
                      :key="choice.carId || choice.fullName"
                      type="button"
                      class="choice-item"
                    >
                      <span>{{ choice.fullName || choice.carId }}</span>
                      <small>{{ choice.plateNumber || "未绑定牌照" }}</small>
                    </button>
                  </div>
                </div>

                <div v-if="message.error" class="inline-alert error">
                  <AlertTriangle :size="16" aria-hidden="true" />
                  <span>{{ message.error.message }}</span>
                </div>

                <div
                  v-for="warning in message.warnings"
                  :key="warning"
                  class="inline-alert warning"
                >
                  <AlertTriangle :size="16" aria-hidden="true" />
                  <span>{{ warning }}</span>
                </div>
              </div>
            </article>
          </div>

          <div class="composer">
            <div class="quick-row">
              <button
                v-for="item in quickQuestions"
                :key="item"
                type="button"
                class="quick-button"
                @click="useQuickQuestion(item)"
              >
                {{ item }}
              </button>
            </div>

            <div class="input-row">
              <el-input
                v-model="question"
                :disabled="sending"
                size="large"
                placeholder="输入问题"
                @keyup.enter="sendQuestion"
              />
              <el-button
                v-if="sending"
                size="large"
                class="stop-button"
                @click="stopStreaming"
              >
                停止
              </el-button>
              <el-button
                v-else
                type="primary"
                size="large"
                class="send-button"
                @click="sendQuestion"
              >
                <Send :size="18" aria-hidden="true" />
                发送
              </el-button>
            </div>
          </div>
        </div>

        <aside class="inspector">
          <section class="inspector-section">
            <div class="section-heading">
              <Activity :size="17" aria-hidden="true" />
              <h2>Trace</h2>
            </div>
            <ol class="trace-list">
              <li v-for="item in traceItems" :key="item.id" :class="item.kind">
                <span></span>
                <p>{{ item.text }}</p>
              </li>
            </ol>
            <p v-if="traceItems.length === 0" class="muted-line">暂无事件</p>
          </section>

          <section class="inspector-section">
            <div class="section-heading">
              <FileText :size="17" aria-hidden="true" />
              <h2>References</h2>
            </div>
            <SqlResultCard
              v-for="reference in assistantReferences.sqlReferences"
              :key="reference.executedSql || reference.sql || reference.chunkContent"
              :reference="reference"
            />
            <div
              v-for="reference in assistantReferences.documentReferences"
              :key="reference.chunkId || reference.documentTitle || reference.chunkContent"
              class="reference-item"
            >
              <strong>{{ reference.documentTitle || "知识库引用" }}</strong>
              <p>{{ reference.chunkContent }}</p>
              <div class="reference-meta">
                <span>{{ reference.retrievalSource || reference.sourceType || "source" }}</span>
              </div>
            </div>
            <p
              v-if="
                !assistantReferences.sqlReferences.length &&
                !assistantReferences.documentReferences.length
              "
              class="muted-line"
            >
              暂无引用
            </p>
          </section>

          <section class="inspector-section compact">
            <div class="section-heading">
              <Settings2 :size="17" aria-hidden="true" />
              <h2>Session</h2>
            </div>
            <dl class="session-list">
              <dt>Conversation</dt>
              <dd>{{ conversationId || "new" }}</dd>
              <dt>Knowledge Base</dt>
              <dd>{{ selectedKnowledgeBase?.name || knowledgeBaseId || "未选择" }}</dd>
              <dt>User</dt>
              <dd>{{ currentUser?.username || "未登录" }}</dd>
            </dl>
          </section>
        </aside>
      </section>
    </main>
  </div>
</template>
