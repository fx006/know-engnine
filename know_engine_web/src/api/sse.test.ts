import { describe, expect, it } from "vitest";

import { parseSsePayload, parseSseText } from "./sse";

describe("SSE parser", () => {
  it("classifies know-engine chat events", () => {
    const events = parseSseText(
      [
        "data: [PROGRESS]:正在识别您的意图...",
        "",
        "data: 第一段回答",
        "",
        'data: [REFERENCE]:[{"chunkId":"chunk-1"}]',
        "",
        "data: [DONE]:conv-1",
        "",
      ].join("\n"),
    );

    expect(events.map((event) => event.kind)).toEqual([
      "progress",
      "answer_delta",
      "reference",
      "done",
    ]);
    expect(events[2].data).toEqual([{ chunkId: "chunk-1" }]);
    expect(events[3].conversationId).toBe("conv-1");
  });

  it("parses card, warning and error payloads", () => {
    expect(parseSsePayload("[CARD]:请先选择车辆").kind).toBe("card");
    expect(parseSsePayload("[WARN]:当前检索证据不足").kind).toBe("warning");
    expect(
      parseSsePayload(
        '[ERROR]:{"code":"LLM_PROVIDER_ERROR","message":"大模型服务暂不可用"}',
      ),
    ).toMatchObject({
      kind: "error",
      data: {
        code: "LLM_PROVIDER_ERROR",
        message: "大模型服务暂不可用",
      },
    });
  });
});
