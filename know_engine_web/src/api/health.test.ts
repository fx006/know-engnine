import { afterEach, describe, expect, it, vi } from "vitest";

import { checkApiHealth, getHealthReport } from "./health";

describe("API health client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns online when health endpoint responds with 2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: "ok" }),
      }),
    );

    await expect(checkApiHealth("http://127.0.0.1:8000/")).resolves.toBe(
      "online",
    );
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health?deep=true",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("returns degraded when external dependencies are unhealthy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: "degraded" }),
      }),
    );

    await expect(checkApiHealth("http://127.0.0.1:8000")).resolves.toBe(
      "degraded",
    );
  });

  it("returns offline when health request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(checkApiHealth("http://127.0.0.1:8000")).resolves.toBe(
      "offline",
    );
  });

  it("loads full component report for admin health panel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          status: "degraded",
          app_name: "know-engine-py",
          environment: "local",
          llm_chat_model: "qwen-plus",
          embedding_model: "text-embedding-v4",
          deep: true,
          components: {
            database: {
              status: "error",
              detail: "数据库连通性检查失败",
              error: "Lost connection",
            },
            redis: {
              status: "ok",
              detail: "Redis 连通性正常",
            },
          },
        }),
      }),
    );

    const report = await getHealthReport("http://127.0.0.1:8000/");

    expect(report.status).toBe("degraded");
    expect(report.components.database.status).toBe("error");
    expect(report.components.database.error).toBe("Lost connection");
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health?deep=true",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("throws a readable error when health endpoint returns non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      }),
    );

    await expect(getHealthReport("http://127.0.0.1:8000")).rejects.toThrow(
      "HTTP 503",
    );
  });
});
