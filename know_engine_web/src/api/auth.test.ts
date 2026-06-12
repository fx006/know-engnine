import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, login } from "./auth";

describe("auth API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("logs in with username and password", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          accessToken: "access-token",
          refreshToken: "refresh-token",
          tokenType: "bearer",
          expiresIn: 1800,
          user: {
            userId: "user-001",
            username: "demo_user",
            nickname: "演示用户",
            role: "user",
            status: "active",
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
          },
        }),
      }),
    );

    const token = await login({
      baseUrl: "http://127.0.0.1:8000/",
      username: "demo_user",
      password: "DemoPassword123",
    });

    expect(token.accessToken).toBe("access-token");
    expect(token.user.userId).toBe("user-001");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: "demo_user",
        password: "DemoPassword123",
      }),
    });
  });

  it("loads current user with bearer token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          userId: "user-001",
          username: "demo_user",
          role: "user",
          status: "active",
          createdAt: "2026-01-01T00:00:00Z",
          updatedAt: "2026-01-01T00:00:00Z",
        }),
      }),
    );

    await expect(
      getCurrentUser({
        baseUrl: "http://127.0.0.1:8000",
        accessToken: "access-token",
      }),
    ).resolves.toMatchObject({
      userId: "user-001",
      username: "demo_user",
    });

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/auth/me", {
      method: "GET",
      headers: {
        Authorization: "Bearer access-token",
      },
    });
  });
});
