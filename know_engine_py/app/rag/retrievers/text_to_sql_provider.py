from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.rag.sql.executor import ReadOnlySqlExecutor
from know_engine_py.app.rag.sql.formatter import SqlResultFormatter
from know_engine_py.app.rag.sql.query_planner import TextToSqlPlanner
from know_engine_py.app.rag.retrievers.text_to_sql import TextToSqlRetriever
from know_engine_py.app.services.table_meta_service import TableMetaService


class TextToSqlRetrieverProvider:
    """Text-to-SQL 检索器提供者。

    它负责把 table_meta、LLM、SQL executor、formatter 和 fallback 文档检索器组装起来。
    chat_graph_builder 只依赖这个 provider，不直接拼 Text-to-SQL 的内部零件。
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        chat_model: Any,
        settings: Settings | None = None,
        document_retriever_provider: Any | None = None,
        max_rows: int = 50,
    ):
        self.db = db
        self.chat_model = chat_model
        self.settings = settings or get_settings()
        self.document_retriever_provider = document_retriever_provider
        self.max_rows = max_rows

    def create(
        self,
        *,
        user_id: str | None = None,
        entities: dict[str, Any] | None = None,
    ) -> TextToSqlRetriever:
        """按当前请求上下文创建 Text-to-SQL retriever。"""
        table_meta_service = TableMetaService(self.db)

        planner = TextToSqlPlanner(
            table_meta_provider=table_meta_service,
            chat_model=self.chat_model,
        )
        executor = ReadOnlySqlExecutor(
            self.db,
            dialect=self._resolve_sql_dialect(),
            max_rows=self.max_rows,
        )
        formatter = SqlResultFormatter()

        return TextToSqlRetriever(
            planner=planner,
            executor=executor,
            formatter=formatter,
            fallback_retriever=self._create_fallback_retriever(),
            user_id=user_id,
            entities=entities,
        )

    def _create_fallback_retriever(self):
        if self.document_retriever_provider is None:
            return None

        # SQL 空结果或失败时，优先降级到当前环境可用的文档检索能力。
        return self.document_retriever_provider.create(strategy="auto")

    def _resolve_sql_dialect(self) -> str:
        database_url = (self.settings.database_url or "").lower()

        if database_url.startswith("sqlite"):
            return "sqlite"

        return "mysql"