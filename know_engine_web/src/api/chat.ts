import type {
  ChatMessage,
  ClarificationChoice,
  RagReference,
} from "../types/chat";
import { extractSseFrames, parseSseText, type SseEvent } from "./sse";

export interface ChatStreamRequest {
  baseUrl: string;
  userId: string;
  knowledgeBaseId: string;
  content: string;
  accessToken?: string;
  conversationId?: string;
  signal?: AbortSignal;
  onEvent: (event: SseEvent) => void;
  onComplete?: (conversationId: string) => void | Promise<void>;
}

export interface ChatConversation {
  conversationId: string;
  userId: string;
  groupId?: string | null;
  knowledgeBaseId?: string | null;
  title?: string | null;
  status: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ChatConversationListRequest {
  baseUrl: string;
  accessToken: string;
}

export interface ChatMessageListRequest {
  baseUrl: string;
  accessToken: string;
  conversationId: string;
}

interface RawChatConversation {
  conversation_id?: string;
  conversationId?: string;
  user_id?: string;
  userId?: string;
  group_id?: string | null;
  groupId?: string | null;
  knowledge_base_id?: string | null;
  knowledgeBaseId?: string | null;
  title?: string | null;
  status?: string;
  created_at?: string;
  createdAt?: string;
  updated_at?: string;
  updatedAt?: string;
}

interface RawChatMessage {
  message_id?: string;
  messageId?: string;
  conversation_id?: string;
  conversationId?: string;
  type?: string;
  content?: string | null;
  rag_references?: RagReference[] | null;
  ragReferences?: RagReference[] | null;
  extra_metadata?: Record<string, unknown> | null;
  extraMetadata?: Record<string, unknown> | null;
}

interface RawClarificationEvent {
  type?: string;
  message?: string;
  items?: ClarificationChoice[];
  data?: ClarificationChoice[];
}

export async function listChatConversations(
  request: ChatConversationListRequest,
): Promise<ChatConversation[]> {
  const response = await fetch(`${normalizeBaseUrl(request.baseUrl)}/chat/list`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${request.accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "会话列表加载失败"));
  }

  const conversations = (await response.json()) as RawChatConversation[];
  return conversations.map(mapChatConversation);
}

export async function listChatMessages(
  request: ChatMessageListRequest,
): Promise<ChatMessage[]> {
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/chat/messages?conversationId=${encodeURIComponent(request.conversationId)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${request.accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "会话消息加载失败"));
  }

  const messages = (await response.json()) as RawChatMessage[];
  return messages.map(mapChatMessage);
}

export function mapChatConversation(raw: RawChatConversation): ChatConversation {
  return {
    conversationId: raw.conversationId || raw.conversation_id || "",
    userId: raw.userId || raw.user_id || "",
    groupId: raw.groupId ?? raw.group_id ?? null,
    knowledgeBaseId: raw.knowledgeBaseId ?? raw.knowledge_base_id ?? null,
    title: raw.title ?? null,
    status: raw.status || "active",
    createdAt: raw.createdAt || raw.created_at,
    updatedAt: raw.updatedAt || raw.updated_at,
  };
}

export function mapChatMessage(raw: RawChatMessage): ChatMessage {
  const extraMetadata = raw.extraMetadata || raw.extra_metadata || {};
  const clarificationEvents = Array.isArray(extraMetadata.clarificationEvents)
    ? (extraMetadata.clarificationEvents as RawClarificationEvent[])
    : [];

  return {
    id: raw.messageId || raw.message_id || crypto.randomUUID(),
    role: raw.type === "user" ? "user" : "assistant",
    content: raw.content || "",
    references: raw.ragReferences || raw.rag_references || [],
    cardMessage: findClarificationMessage(clarificationEvents),
    cardChoices: findClarificationChoices(clarificationEvents),
    warnings: findClarificationWarnings(clarificationEvents),
  };
}

export async function streamChat(request: ChatStreamRequest): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (request.accessToken) {
    headers.Authorization = `Bearer ${request.accessToken}`;
  }

  const response = await fetch(`${normalizeBaseUrl(request.baseUrl)}/chat/send`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      userId: request.userId,
      content: request.content,
      conversationId: request.conversationId || undefined,
      knowledgeBaseId: request.knowledgeBaseId || undefined,
    }),
    signal: request.signal,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(formatHttpError(response.status, body || response.statusText));
  }

  if (!response.body) {
    throw new Error("当前浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const { frames, rest } = extractSseFrames(buffer);
    buffer = rest;

    for (const frame of frames) {
      for (const event of parseSseText(`${frame}\n\n`)) {
        request.onEvent(event);
        if (event.kind === "done" && event.conversationId) {
          await request.onComplete?.(event.conversationId);
        }
      }
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    for (const event of parseSseText(buffer)) {
      request.onEvent(event);
      if (event.kind === "done" && event.conversationId) {
        await request.onComplete?.(event.conversationId);
      }
    }
  }
}

export function formatHttpError(status: number, body: string): string {
  if (status >= 500) {
    return "后端服务异常，请检查 FastAPI 日志和数据库/Redis/MinIO/ES 等依赖状态";
  }
  if (status === 404) {
    return "接口不存在或知识库不存在，请检查 API 地址和 knowledgeBaseId";
  }
  if (status === 403) {
    return "当前用户无权访问该知识库";
  }
  if (status === 400) {
    return body || "请求参数不正确";
  }
  return `HTTP ${status}: ${body}`;
}

function findClarificationMessage(events: RawClarificationEvent[]): string | undefined {
  const cardEvent = events.find((event) => event.type === "CARD");
  return cardEvent?.message || undefined;
}

function findClarificationChoices(
  events: RawClarificationEvent[],
): ClarificationChoice[] | undefined {
  const choiceEvent = events.find((event) =>
    String(event.type || "").startsWith("CARD_CHOICE"),
  );
  return choiceEvent?.items || choiceEvent?.data || undefined;
}

function findClarificationWarnings(events: RawClarificationEvent[]): string[] {
  return events
    .filter((event) => event.type === "WARN" && event.message)
    .map((event) => String(event.message));
}

async function readErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const body = await response.text();
  if (!body) {
    return fallback;
  }

  try {
    const data = JSON.parse(body) as { detail?: string };
    return data.detail || fallback;
  } catch {
    return body;
  }
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}
