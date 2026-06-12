export interface AuthUser {
  userId: string;
  username: string;
  nickname?: string | null;
  role: string;
  status: string;
  lastLoginAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AuthToken {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user: AuthUser;
}

export interface LoginRequest {
  baseUrl: string;
  username: string;
  password: string;
}

export interface AuthenticatedRequest {
  baseUrl: string;
  accessToken: string;
}

export async function login(request: LoginRequest): Promise<AuthToken> {
  const response = await fetch(`${normalizeBaseUrl(request.baseUrl)}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username: request.username,
      password: request.password,
    }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "登录失败，请检查用户名和密码"));
  }

  return (await response.json()) as AuthToken;
}

export async function getCurrentUser(
  request: AuthenticatedRequest,
): Promise<AuthUser> {
  const response = await fetch(`${normalizeBaseUrl(request.baseUrl)}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${request.accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "登录状态已失效，请重新登录"));
  }

  return (await response.json()) as AuthUser;
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
