import { describe, expect, it } from "vitest";

import type { RagReference } from "../types/chat";
import {
  getSqlDisplayText,
  isSqlReference,
  splitReferencesBySource,
} from "./references";

describe("reference helpers", () => {
  it("separates SQL references from document references", () => {
    const references: RagReference[] = [
      {
        sourceType: "text2sql",
        chunkContent: "结构化查询结果：Model Y 指导价 299900",
        sql: "select guide_price from car_info",
      },
      {
        documentTitle: "车主指南",
        chunkId: "chunk-001",
        chunkContent: "官方客服电话为 400-008-2888。",
      },
    ];

    const result = splitReferencesBySource(references);

    expect(result.sqlReferences).toHaveLength(1);
    expect(result.documentReferences).toHaveLength(1);
    expect(isSqlReference(result.sqlReferences[0])).toBe(true);
  });

  it("uses executed SQL before planned SQL for display", () => {
    expect(
      getSqlDisplayText({
        sourceType: "text2sql",
        sql: "select * from car_info",
        executedSql: "SELECT * FROM car_info LIMIT 21",
      }),
    ).toBe("SELECT * FROM car_info LIMIT 21");
  });
});
