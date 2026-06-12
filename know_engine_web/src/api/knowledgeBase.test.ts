import { afterEach, describe, expect, it, vi } from "vitest";

import { listKnowledgeBases } from "./knowledgeBase";

describe("knowledge base API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads current user's knowledge bases with bearer token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue([
          {
            knowledgeBaseId: "kb-001",
            groupId: "group-001",
            name: "汽车售后知识库",
            description: "演示知识库",
            visibility: "group",
            createdBy: "user-001",
            status: "active",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
          },
        ]),
      }),
    );

    const knowledgeBases = await listKnowledgeBases({
      baseUrl: "http://127.0.0.1:8000/",
      accessToken: "access-token",
    });

    expect(knowledgeBases).toHaveLength(1);
    expect(knowledgeBases[0].knowledgeBaseId).toBe("kb-001");
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/knowledge-bases",
      {
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      },
    );
  });
});
