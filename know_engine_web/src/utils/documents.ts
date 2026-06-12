import type { KnowledgeDocument } from "../api/document";

export type DocumentStatusFilter = "all" | "ready" | "processing" | "failed";

export interface DocumentStatusFilterOption {
  value: DocumentStatusFilter;
  label: string;
}

export interface DocumentFilter {
  keyword: string;
  statusFilter: DocumentStatusFilter;
}

export const statusFilterOptions: DocumentStatusFilterOption[] = [
  { value: "all", label: "全部" },
  { value: "ready", label: "可用" },
  { value: "processing", label: "处理中" },
  { value: "failed", label: "失败" },
];

const READY_STATUSES = new Set(["success", "vector_stored", "chunked", "converted"]);
const PROCESSING_STATUSES = new Set([
  "uploaded",
  "running",
  "queued",
  "pending",
  "converting",
  "indexing",
  "processing",
]);
const FAILED_STATUSES = new Set(["failed", "error"]);

export function filterDocuments(
  documents: KnowledgeDocument[],
  filter: DocumentFilter,
): KnowledgeDocument[] {
  const keyword = normalize(filter.keyword);

  return documents.filter((document) => {
    if (!matchesStatus(document.status, filter.statusFilter)) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    return searchableText(document).includes(keyword);
  });
}

export function matchesStatus(
  status: string | undefined,
  filter: DocumentStatusFilter,
): boolean {
  if (filter === "all") {
    return true;
  }

  const normalizedStatus = normalizeStatus(status);
  if (filter === "ready") {
    return READY_STATUSES.has(normalizedStatus);
  }
  if (filter === "processing") {
    return PROCESSING_STATUSES.has(normalizedStatus);
  }

  return FAILED_STATUSES.has(normalizedStatus);
}

function searchableText(document: KnowledgeDocument): string {
  return normalize(
    [
      document.doc_title,
      document.description,
      document.status,
      document.knowledge_base_type,
      document.upload_user,
    ]
      .filter(Boolean)
      .join(" "),
  );
}

function normalizeStatus(status: string | undefined): string {
  return normalize(status).replace(/-/g, "_");
}

function normalize(value: string | null | undefined): string {
  return String(value || "").trim().toLowerCase();
}
