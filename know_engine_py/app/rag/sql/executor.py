from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlglot import exp

from know_engine_py.app.rag.sql.safety import SqlSafetyValidator


@dataclass(slots=True)
class SqlExecutionResult:
    """只读 SQL 执行结果。"""

    success: bool
    sql: str
    executed_sql: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    truncated: bool = False
    error: str = ""


class ReadOnlySqlExecutor:
    """Text-to-SQL 的只读 SQL 执行器。

    执行前会再次走 SqlSafetyValidator。不能因为 planner 校验过，
    就默认传进来的 SQL 永远可信。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        safety_validator: SqlSafetyValidator | None = None,
        max_rows: int = 50,
        dialect: str = "mysql",
    ):
        if max_rows <= 0:
            raise ValueError("max_rows 必须大于 0")

        self.session = session
        self.safety_validator = safety_validator or SqlSafetyValidator(dialect=dialect)
        self.max_rows = max_rows
        self.dialect = dialect

    async def execute(
        self,
        sql: str,
        *,
        allowed_tables: list[str],
    ) -> SqlExecutionResult:
        """校验并执行只读 SQL。"""
        safety_result = self.safety_validator.validate(
            sql,
            allowed_tables=allowed_tables,
        )

        if not safety_result.valid:
            return SqlExecutionResult(
                success=False,
                sql=sql,
                tables=safety_result.tables or [],
                error=safety_result.reason,
            )

        try:
            executed_sql = self._apply_row_limit(sql)
        except ValueError as exc:
            return SqlExecutionResult(
                success=False,
                sql=sql,
                tables=safety_result.tables or [],
                error=str(exc),
            )

        try:
            result = await self.session.execute(text(executed_sql))
            columns = list(result.keys())

            # 多取一行用于判断是否被截断，真正返回仍只返回 max_rows 行。
            fetched_rows = result.mappings().fetchmany(self.max_rows + 1)
            truncated = len(fetched_rows) > self.max_rows
            rows = [dict(row) for row in fetched_rows[: self.max_rows]]
        except SQLAlchemyError:
            return SqlExecutionResult(
                success=False,
                sql=sql,
                executed_sql=executed_sql,
                tables=safety_result.tables or [],
                error="SQL 执行失败",
            )

        return SqlExecutionResult(
            success=True,
            sql=sql,
            executed_sql=executed_sql,
            rows=rows,
            columns=columns,
            tables=safety_result.tables or [],
            truncated=truncated,
        )

    def _apply_row_limit(self, sql: str) -> str:
        """给查询加结果上限，避免 LLM 生成无边界大查询。"""
        try:
            statement = sqlglot.parse_one(sql, read=self.dialect)
        except sqlglot.errors.ParseError as exc:
            raise ValueError("SQL 限制行数失败") from exc

        target_limit = self.max_rows + 1
        existing_limit = self._read_limit_value(statement)

        if existing_limit is not None and existing_limit <= target_limit:
            return statement.sql(dialect=self.dialect)

        return statement.limit(target_limit).sql(dialect=self.dialect)

    def _read_limit_value(self, statement: exp.Expression) -> int | None:
        limit = statement.args.get("limit")
        if not limit or not limit.expression:
            return None

        value = limit.expression
        if isinstance(value, exp.Literal) and not value.is_string:
            try:
                return int(value.this)
            except (TypeError, ValueError):
                return None

        return None