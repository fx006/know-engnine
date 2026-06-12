import { describe, expect, it } from "vitest";

import type { KnowledgeDocument } from "../api/document";
import { filterDocuments, statusFilterOptions } from "./documents";

const documents: KnowledgeDocument[] = [
  {
    doc_id: 1,
    doc_title: "售后服务规则.md",
    description: "投诉、客服电话和服务流程",
    status: "VECTOR_STORED",
    knowledge_base_type: "markdown",
  },
  {
    doc_id: 2,
    doc_title: "车主指南.pdf",
    description: "车辆功能说明",
    status: "RUNNING",
    knowledge_base_type: "pdf",
  },
  {
    doc_id: 3,
    doc_title: "保养手册.docx",
    description: "保养周期",
    status: "FAILED",
    knowledge_base_type: "word",
  },
];

describe("document filtering helpers", () => {
  it("filters documents by keyword across title and description", () => {
    const result = filterDocuments(documents, {
      keyword: "客服",
      statusFilter: "all",
    });

    expect(result.map((document) => document.doc_id)).toEqual([1]);
  });

  it("filters documents by operational status group", () => {
    const processing = filterDocuments(documents, {
      keyword: "",
      statusFilter: "processing",
    });
    const failed = filterDocuments(documents, {
      keyword: "",
      statusFilter: "failed",
    });

    expect(processing.map((document) => document.doc_id)).toEqual([2]);
    expect(failed.map((document) => document.doc_id)).toEqual([3]);
  });

  it("exposes stable status filter labels", () => {
    expect(statusFilterOptions.map((option) => option.value)).toEqual([
      "all",
      "ready",
      "processing",
      "failed",
    ]);
  });
});
