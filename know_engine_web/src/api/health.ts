export type HealthStatus = "online" | "degraded" | "offline";

export const HEALTH_REQUEST_TIMEOUT_MS = 12_000;

export type HealthComponentStatus = "ok" | "configured" | "skipped" | "error";

export interface HealthComponent {
  status: HealthComponentStatus | string;
  detail: string;
  error?: string;
  bucket?: string;
  [key: string]: unknown;
}

export interface HealthReport {
  status: "ok" | "degraded" | string;
  app_name: string;
  environment: string;
  llm_chat_model: string;
  embedding_model: string;
  deep: boolean;
  components: Record<string, HealthComponent>;
}

export async function checkApiHealth(baseUrl: string): Promise<HealthStatus> {
  try {
    const data = await getHealthReport(baseUrl, true);
    return data.status === "ok" ? "online" : "degraded";
  } catch {
    return "offline";
  }
}

export async function getHealthReport(
  baseUrl: string,
  deep = true,
  timeoutMs = HEALTH_REQUEST_TIMEOUT_MS,
): Promise<HealthReport> {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(
      `${normalizeBaseUrl(baseUrl)}/health${deep ? "?deep=true" : ""}`,
      {
        method: "GET",
        signal: controller.signal,
      },
    );
  } finally {
    globalThis.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new Error(`健康检查请求失败：HTTP ${response.status}`);
  }

  const data = (await response.json()) as Partial<HealthReport>;
  return {
    status: data.status || "degraded",
    app_name: data.app_name || "know-engine-py",
    environment: data.environment || "unknown",
    llm_chat_model: data.llm_chat_model || "unknown",
    embedding_model: data.embedding_model || "unknown",
    deep: Boolean(data.deep),
    components: data.components || {},
  };
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}
