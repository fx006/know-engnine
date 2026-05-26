from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr


class TextToSqlRetriever(BaseRetriever):
    """结构化数据检索器。

    对齐 Java KnowEngineSqlDatabaseContentRetriever：
    先走 Text-to-SQL；如果 SQL 规划失败、执行失败或结果为空，可降级到知识库检索。
    """

    allowed_tables: list[str] | None = None
    user_id: str | None = None
    entities: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _planner: Any = PrivateAttr()
    _executor: Any = PrivateAttr()
    _formatter: Any = PrivateAttr()
    _fallback_retriever: Any = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        planner: Any,
        executor: Any,
        formatter: Any,
        fallback_retriever: Any | None = None,
        **data: Any,
    ):
        self._validate_dependency(planner, method_name="plan", name="planner")
        self._validate_dependency(executor, method_name="execute", name="executor")
        self._validate_dependency(formatter, method_name="format", name="formatter")

        if fallback_retriever is not None:
            self._validate_dependency(
                fallback_retriever,
                method_name="ainvoke",
                name="fallback_retriever",
            )

        super().__init__(**data)
        self._planner = planner
        self._executor = executor
        self._formatter = formatter
        self._fallback_retriever = fallback_retriever

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        raise NotImplementedError("TextToSqlRetriever 只支持异步检索，请使用 ainvoke()")

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        plan = await self._planner.plan(
            question=query,
            user_id=self.user_id,
            entities=self.entities,
        )

        if not plan.valid:
            failure_document = self._build_failure_document(
                content=f"结构化查询失败：{plan.reason}",
                sql=plan.sql,
                tables=plan.tables or [],
                error=plan.reason,
            )
            return await self._fallback_or_default(
                query=query,
                reason=plan.reason,
                default_document=failure_document,
            )

        allowed_tables = self._resolve_allowed_tables(plan)
        if not allowed_tables:
            failure_document = self._build_failure_document(
                content="结构化查询失败：缺少可查询的表白名单",
                sql=plan.sql,
                tables=plan.tables or [],
                error="缺少可查询的表白名单",
            )
            return await self._fallback_or_default(
                query=query,
                reason="缺少可查询的表白名单",
                default_document=failure_document,
            )

        result = await self._executor.execute(
            plan.sql,
            allowed_tables=allowed_tables,
        )

        content = self._formatter.format(result)

        document = self._build_document(
            content=content,
            metadata={
                "retrievalSource": "text2sql",
                "sqlValid": True,
                "sql": plan.sql,
                "executedSql": result.executed_sql,
                "tables": result.tables,
                "rowCount": len(result.rows),
                "truncated": result.truncated,
                "success": result.success,
                "error": result.error,
            },
        )

        if not result.success:
            return await self._fallback_or_default(
                query=query,
                reason=result.error or "SQL 执行失败",
                default_document=document,
            )

        if not result.rows:
            return await self._fallback_or_default(
                query=query,
                reason="SQL 查询结果为空",
                default_document=document,
            )

        return [document]

    async def _fallback_or_default(
        self,
        *,
        query: str,
        reason: str,
        default_document: Document,
    ) -> list[Document]:
        """SQL 不可用时降级到知识库检索；没有 fallback 时返回原 SQL 结果文档。"""
        if self._fallback_retriever is None:
            return [default_document]

        try:
            documents = await self._fallback_retriever.ainvoke(query)
        except Exception as exc:
            fallback_error_document = self._copy_document_with_metadata(
                default_document,
                {
                    "fallbackAttempted": True,
                    "fallbackError": str(exc),
                },
            )
            return [fallback_error_document]

        if not documents:
            return [default_document]

        return [
            self._copy_document_with_metadata(
                document,
                {
                    "fallbackFrom": "text2sql",
                    "fallbackReason": reason,
                },
            )
            for document in documents
        ]

    def _build_failure_document(
        self,
        *,
        content: str,
        sql: str,
        tables: list[str],
        error: str,
    ) -> Document:
        return self._build_document(
            content=content,
            metadata={
                "retrievalSource": "text2sql",
                "sqlValid": False,
                "sql": sql,
                "tables": tables,
                "error": error,
            },
        )

    def _build_document(
        self,
        *,
        content: str,
        metadata: Mapping[str, Any],
    ) -> Document:
        return Document(
            page_content=content,
            metadata=dict(metadata),
        )

    def _copy_document_with_metadata(
        self,
        document: Document,
        metadata: Mapping[str, Any],
    ) -> Document:
        merged_metadata = dict(document.metadata or {})
        merged_metadata.update(metadata)

        return Document(
            id=document.id,
            page_content=document.page_content,
            metadata=merged_metadata,
        )

    def _validate_dependency(
        self,
        dependency: Any,
        *,
        method_name: str,
        name: str,
    ) -> None:
        if not callable(getattr(dependency, method_name, None)):
            raise ValueError(f"{name} 必须提供 {method_name}() 方法")

    def _resolve_allowed_tables(self, plan: Any) -> list[str]:
        if self.allowed_tables is not None:
            return self.allowed_tables

        return list(plan.allowed_tables or [])