export interface KnowledgeBase {
  knowledgeBaseId: string;
  groupId: string;
  name: string;
  description?: string | null;
  visibility: string;
  createdBy: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeBaseListRequest {
  baseUrl: string;
  accessToken: string;
}

export async function listKnowledgeBases(
  request: KnowledgeBaseListRequest,
): Promise<KnowledgeBase[]> {
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/knowledge-bases`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${request.accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "知识库列表加载失败"));
  }

  return (await response.json()) as KnowledgeBase[];
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
