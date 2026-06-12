export interface KnowledgeDocument {
  doc_id: number;
  doc_title: string;
  upload_user?: string | null;
  doc_url?: string | null;
  converted_doc_url?: string | null;
  status: string;
  accessible_by?: string | null;
  description?: string | null;
  knowledge_base_type?: string | null;
  group_id?: string | null;
  knowledge_base_id?: string | null;
  file_object_id?: string | null;
  extension?: Record<string, unknown> | null;
  conversionQueued?: boolean;
  conversionTaskId?: string | null;
  conversionQueueError?: string | null;
}

export interface DocumentSplitResult {
  documentId: number;
  segmentCount: number;
  indexQueued: boolean;
  indexTaskId?: string | null;
  indexQueueError?: string | null;
}

export interface KnowledgeSegment {
  id?: number;
  segment_id?: number;
  document_id: number;
  chunk_id?: string | null;
  chunk_order: number;
  text: string;
  status: string;
  skip_embedding: number;
  extra_metadata?: Record<string, unknown> | null;
}

export interface DocumentTask {
  taskId: string;
  documentId: number;
  taskType: string;
  status: string;
  celeryTaskId?: string | null;
  currentAttempt: number;
  maxAttempts: number;
  lastError?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  nextRetryAt?: string | null;
  taskMetadata?: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface ImportDocumentRequest {
  baseUrl: string;
  accessToken: string;
  knowledgeBaseId: string;
  file: File;
  docTitle?: string;
  description?: string;
}

export interface ListDocumentsRequest {
  baseUrl: string;
  accessToken: string;
  knowledgeBaseId: string;
}

export interface SplitDocumentRequest {
  baseUrl: string;
  accessToken: string;
  documentId: number;
}

export interface ListSegmentsRequest {
  baseUrl: string;
  documentId: number;
}

export interface ListDocumentTasksRequest {
  baseUrl: string;
  accessToken: string;
  documentId: number;
}

export async function importDocument(
  request: ImportDocumentRequest,
): Promise<KnowledgeDocument> {
  const body = new FormData();
  body.append("file", request.file);
  body.append("knowledgeBaseId", request.knowledgeBaseId);
  if (request.docTitle?.trim()) {
    body.append("docTitle", request.docTitle.trim());
  }
  if (request.description?.trim()) {
    body.append("description", request.description.trim());
  }

  const response = await fetch(`${normalizeBaseUrl(request.baseUrl)}/documents/import`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${request.accessToken}`,
    },
    body,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "文档导入失败"));
  }

  return (await response.json()) as KnowledgeDocument;
}

export async function listDocuments(
  request: ListDocumentsRequest,
): Promise<KnowledgeDocument[]> {
  const params = new URLSearchParams({
    knowledgeBaseId: request.knowledgeBaseId,
  });
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/documents?${params.toString()}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${request.accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "文档列表加载失败"));
  }

  return (await response.json()) as KnowledgeDocument[];
}

export async function splitDocument(
  request: SplitDocumentRequest,
): Promise<DocumentSplitResult> {
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/documents/${request.documentId}/split`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${request.accessToken}`,
      },
      body: JSON.stringify({
        splitType: "TITLE",
        chunkSize: 800,
        overlap: 80,
        titleLevel: 1,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "文档切分失败"));
  }

  return (await response.json()) as DocumentSplitResult;
}

export async function listDocumentSegments(
  request: ListSegmentsRequest,
): Promise<KnowledgeSegment[]> {
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/documents/${request.documentId}/segments`,
    {
      method: "GET",
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "文档切分结果加载失败"));
  }

  return (await response.json()) as KnowledgeSegment[];
}

export async function listDocumentTasks(
  request: ListDocumentTasksRequest,
): Promise<DocumentTask[]> {
  const response = await fetch(
    `${normalizeBaseUrl(request.baseUrl)}/documents/${request.documentId}/tasks`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${request.accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "文档任务状态加载失败"));
  }

  return (await response.json()) as DocumentTask[];
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
