from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.document import TableMetaModel


class TableMetaService:
    """结构化表元数据服务。

    Text-to-SQL 不应直接暴露整库表结构给 LLM。
    这里负责读取 table_meta，形成允许查询的表白名单和提示词可用的表结构上下文。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_table_meta(self) -> list[TableMetaModel]:
        """按表名稳定返回全部表元数据。"""
        result = await self.session.execute(
            select(TableMetaModel).order_by(TableMetaModel.table_name.asc())
        )
        return list(result.scalars().all())

    async def list_allowed_table_names(self) -> list[str]:
        """返回允许 Text-to-SQL 使用的逻辑表名。"""
        table_metas = await self.list_table_meta()
        return [item.table_name for item in table_metas if item.table_name]

    async def build_database_context(self) -> str:
        """构建给 LLM 的数据库结构上下文。

        这里只输出 table_meta 中登记过的表，避免 LLM 查询平台内部表。
        """
        table_metas = await self.list_table_meta()
        if not table_metas:
            return ""

        blocks: list[str] = []
        for table_meta in table_metas:
            blocks.append(self._format_table_meta(table_meta))

        return "\n\n".join(blocks)

    def _format_table_meta(self, table_meta: TableMetaModel) -> str:
        lines = [f"表名：{table_meta.table_name}"]

        if table_meta.description:
            lines.append(f"说明：{table_meta.description}")

        columns_info = table_meta.columns_info or []
        if columns_info:
            lines.append("字段：")
            for column in columns_info:
                lines.append(f"- {self._format_column(column)}")

        if table_meta.create_sql:
            # create_sql 作为补充结构信息，后续 SQL 生成链可选择是否使用。
            lines.append("建表语句：")
            lines.append(table_meta.create_sql)

        return "\n".join(lines)

    def _format_column(self, column: dict) -> str:
        name = self._pick(column, "name", "columnName", "column_name")
        column_type = self._pick(column, "type", "columnType", "data_type")
        comment = self._pick(column, "comment", "description", "originalHeader")

        parts = [str(name)] if name else ["未知字段"]

        if column_type:
            parts.append(f"类型：{column_type}")

        if comment:
            parts.append(f"说明：{comment}")

        return "，".join(parts)

    def _pick(self, data: dict, *keys: str) -> object | None:
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        return None