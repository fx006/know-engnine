import type { SseErrorPayload } from "../api/sse";

export interface RagReference {
  documentId?: string | null;
  url?: string | null;
  documentTitle?: string | null;
  chunkId?: string | null;
  chunkContent?: string;
  retrievalSource?: string;
  sourceType?: string;
  sql?: string;
  executedSql?: string;
  tables?: string[];
  rowCount?: number;
  truncated?: boolean | null;
  success?: boolean | null;
  error?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ClarificationChoice {
  carId?: string;
  fullName?: string;
  plateNumber?: string;
  imageUrl?: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  references?: RagReference[];
  cardMessage?: string;
  cardChoices?: ClarificationChoice[];
  warnings?: string[];
  error?: SseErrorPayload;
}

export interface StreamTraceItem {
  id: string;
  kind: string;
  text: string;
}
