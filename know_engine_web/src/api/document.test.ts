import { afterEach, describe, expect, it, vi } from "vitest";

import {
  importDocument,
  listDocuments,
  listDocumentSegments,
  listDocumentTasks,
  splitDocument,
} from "./document";

describe("document API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("imports a quick document into selected knowledge base", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          doc_id: 12,
          doc_title: "owner_guide.md",
          status: "CONVERTED",
          knowledge_base_id: "kb-001",
          conversionQueued: false,
        }),
      }),
    );

    const file = new File(["# hello"], "owner_guide.md", {
      type: "text/markdown",
    });
    const document = await importDocument({
      baseUrl: "http://127.0.0.1:8000/",
      accessToken: "access-token",
      knowledgeBaseId: "kb-001",
      file,
    });

    expect(document.doc_id).toBe(12);
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/documents/import",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer access-token",
        },
      }),
    );
    const body = vi.mocked(fetch).mock.calls[0][1]?.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("knowledgeBaseId")).toBe("kb-001");
  });

  it("splits imported document with default title strategy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          documentId: 12,
          segmentCount: 3,
          indexQueued: true,
          indexTaskId: "task-001",
        }),
      }),
    );

    const result = await splitDocument({
      baseUrl: "http://127.0.0.1:8000",
      accessToken: "access-token",
      documentId: 12,
    });

    expect(result.segmentCount).toBe(3);
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/documents/12/split",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
        body: JSON.stringify({
          splitType: "TITLE",
          chunkSize: 800,
          overlap: 80,
          titleLevel: 1,
        }),
      }),
    );
  });

  it("loads segments and document tasks", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: vi.fn().mockResolvedValue([
            {
              id: 1,
              document_id: 12,
              chunk_id: "chunk-001",
              chunk_order: 1,
              text: "正文",
              status: "STORED",
              skip_embedding: 0,
            },
          ]),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: vi.fn().mockResolvedValue([
            {
              taskId: "task-001",
              documentId: 12,
              taskType: "index",
              status: "success",
              currentAttempt: 1,
              maxAttempts: 3,
              createdAt: "2026-01-01T00:00:00Z",
              updatedAt: "2026-01-01T00:00:00Z",
            },
          ]),
        }),
    );

    await expect(
      listDocumentSegments({
        baseUrl: "http://127.0.0.1:8000",
        documentId: 12,
      }),
    ).resolves.toHaveLength(1);
    await expect(
      listDocumentTasks({
        baseUrl: "http://127.0.0.1:8000",
        accessToken: "access-token",
        documentId: 12,
      }),
    ).resolves.toHaveLength(1);
  });

  it("lists documents by selected knowledge base", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue([
          {
            doc_id: 12,
            doc_title: "owner_guide.md",
            status: "VECTOR_STORED",
            knowledge_base_id: "kb-001",
          },
        ]),
      }),
    );

    const documents = await listDocuments({
      baseUrl: "http://127.0.0.1:8000/",
      accessToken: "access-token",
      knowledgeBaseId: "kb-001",
    });

    expect(documents).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/documents?knowledgeBaseId=kb-001",
      expect.objectContaining({
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      }),
    );
  });
});
