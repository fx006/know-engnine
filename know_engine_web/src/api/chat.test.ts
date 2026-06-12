import { afterEach, describe, expect, it, vi } from "vitest";

import {
  formatHttpError,
  listChatConversations,
  listChatMessages,
  mapChatMessage,
  streamChat,
} from "./chat";

describe("chat API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps backend 500 to an operator friendly message", () => {
    expect(formatHttpError(500, "Internal Server Error")).toBe(
      "后端服务异常，请检查 FastAPI 日志和数据库/Redis/MinIO/ES 等依赖状态",
    );
  });

  it("keeps permission and missing resource errors actionable", () => {
    expect(formatHttpError(403, "Forbidden")).toBe("当前用户无权访问该知识库");
    expect(formatHttpError(404, "Not Found")).toBe(
      "接口不存在或知识库不存在，请检查 API 地址和 knowledgeBaseId",
    );
  });

  it("sends bearer token when access token is provided", async () => {
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body,
      }),
    );

    await streamChat({
      baseUrl: "http://127.0.0.1:8000/",
      userId: "user-001",
      knowledgeBaseId: "kb-001",
      accessToken: "access-token",
      content: "官方客服电话是多少？",
      onEvent: vi.fn(),
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat/send",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
      }),
    );
  });

  it("notifies when stream is completed so callers can reload persisted messages", async () => {
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            [
              "data: 回答内容",
              "",
              'data: [REFERENCE]:[{"chunkId":"chunk-1"}]',
              "",
              "data: [DONE]:conv-1",
              "",
            ].join("\n"),
          ),
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body,
      }),
    );

    const onComplete = vi.fn();
    await streamChat({
      baseUrl: "http://127.0.0.1:8000/",
      userId: "user-001",
      knowledgeBaseId: "kb-001",
      content: "官方客服电话是多少？",
      onEvent: vi.fn(),
      onComplete,
    });

    expect(onComplete).toHaveBeenCalledWith("conv-1");
  });

  it("maps persisted assistant messages back to frontend cards and references", () => {
    const message = mapChatMessage({
      message_id: "msg-1",
      conversation_id: "conv-1",
      type: "assistant",
      content: "请选择车辆",
      rag_references: [
        {
          documentTitle: "售后服务规则",
          chunkContent: "官方客服电话为 400-008-2888。",
        },
      ],
      extra_metadata: {
        clarificationEvents: [
          { type: "CARD", message: "请选择车辆" },
          {
            type: "CARD_CHOICE_MYCAR",
            items: [{ carId: "car-1", fullName: "Model Y" }],
          },
        ],
      },
    });

    expect(message).toMatchObject({
      id: "msg-1",
      role: "assistant",
      content: "请选择车辆",
      cardMessage: "请选择车辆",
      cardChoices: [{ carId: "car-1", fullName: "Model Y" }],
      references: [
        {
          documentTitle: "售后服务规则",
          chunkContent: "官方客服电话为 400-008-2888。",
        },
      ],
    });
  });

  it("loads conversation messages with bearer token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue([
          {
            message_id: "msg-user",
            conversation_id: "conv-1",
            type: "user",
            content: "官方客服电话是多少？",
          },
        ]),
      }),
    );

    const messages = await listChatMessages({
      baseUrl: "http://127.0.0.1:8000/",
      accessToken: "access-token",
      conversationId: "conv-1",
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat/messages?conversationId=conv-1",
      expect.objectContaining({
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      }),
    );
    expect(messages[0]).toMatchObject({
      id: "msg-user",
      role: "user",
      content: "官方客服电话是多少？",
    });
  });

  it("loads recent conversations and converts snake case fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue([
          {
            conversation_id: "conv-1",
            user_id: "user-1",
            group_id: "group-1",
            knowledge_base_id: "kb-1",
            title: "售后咨询",
            status: "active",
            created_at: "2026-06-11T08:00:00Z",
            updated_at: "2026-06-11T08:05:00Z",
          },
        ]),
      }),
    );

    const conversations = await listChatConversations({
      baseUrl: "http://127.0.0.1:8000/",
      accessToken: "access-token",
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat/list",
      expect.objectContaining({
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      }),
    );
    expect(conversations[0]).toMatchObject({
      conversationId: "conv-1",
      userId: "user-1",
      groupId: "group-1",
      knowledgeBaseId: "kb-1",
      title: "售后咨询",
    });
  });
});
