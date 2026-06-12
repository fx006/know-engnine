import type { RagReference } from "../types/chat";

export interface SplitReferencesResult {
  sqlReferences: RagReference[];
  documentReferences: RagReference[];
}

export function isSqlReference(reference: RagReference): boolean {
  const sourceType = reference.sourceType?.toLowerCase();
  const retrievalSource = reference.retrievalSource?.toLowerCase();
  return sourceType === "text2sql" || retrievalSource === "text2sql";
}

export function splitReferencesBySource(
  references: RagReference[] | undefined,
): SplitReferencesResult {
  const sqlReferences: RagReference[] = [];
  const documentReferences: RagReference[] = [];

  for (const reference of references || []) {
    if (isSqlReference(reference)) {
      sqlReferences.push(reference);
    } else {
      documentReferences.push(reference);
    }
  }

  return { sqlReferences, documentReferences };
}

export function getSqlDisplayText(reference: RagReference): string {
  return reference.executedSql || reference.sql || "";
}
