from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


@dataclass(slots=True)
class SqlSafetyResult:
    """SQL 安全校验结果。"""

    valid: bool
    reason: str = ""
    tables: list[str] | None = None


class SqlSafetyValidator:
    """Text-to-SQL 执行前的安全门禁。

    LLM 生成 SQL 后，不能直接交给数据库执行。
    这里先做只读校验、单语句校验和 table_meta 白名单校验。
    """

    def __init__(self, dialect: str = "mysql"):
        self.dialect = dialect

    def validate(
        self,
        sql: str,
        *,
        allowed_tables: list[str],
    ) -> SqlSafetyResult:
        if not sql or not sql.strip():
            return SqlSafetyResult(valid=False, reason="SQL 不能为空", tables=[])

        try:
            statements = sqlglot.parse(sql, read=self.dialect)
        except sqlglot.errors.ParseError:
            return SqlSafetyResult(valid=False, reason="SQL 解析失败", tables=[])

        if len(statements) != 1:
            return SqlSafetyResult(valid=False, reason="只允许执行一条 SQL", tables=[])

        statement = statements[0]

        if not self._is_readonly_query(statement):
            return SqlSafetyResult(valid=False, reason="只允许执行只读 SELECT 查询", tables=[])

        tables = self._extract_table_names(statement)
        if not tables:
            return SqlSafetyResult(valid=False, reason="SQL 中没有识别到查询表", tables=[])

        allowed_table_set = set(allowed_tables)
        unknown_tables = [table for table in tables if table not in allowed_table_set]
        if unknown_tables:
            return SqlSafetyResult(
                valid=False,
                reason=f"SQL 访问了未授权表：{', '.join(unknown_tables)}",
                tables=tables,
            )

        return SqlSafetyResult(valid=True, tables=tables)

    def _is_readonly_query(self, statement: exp.Expression) -> bool:
        """只允许 SELECT 类查询，避免 LLM 生成写库或 DDL SQL。"""
        if not isinstance(statement, (exp.Select, exp.Union)):
            return False

        forbidden_nodes = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Drop,
            exp.Create,
            exp.Alter,
            exp.Merge,
            exp.TruncateTable,
        )
        return not any(statement.find(node_type) for node_type in forbidden_nodes)

    def _extract_table_names(self, statement: exp.Expression) -> list[str]:
        """提取真实表名，并排除 WITH 子句里的临时 CTE 名称。"""
        cte_names = {
            cte.alias_or_name
            for cte in statement.find_all(exp.CTE)
            if cte.alias_or_name
        }

        table_names: list[str] = []
        seen: set[str] = set()

        for table in statement.find_all(exp.Table):
            table_name = table.name

            if not table_name:
                continue

            # 只有裸表名才可能是 CTE 引用
            if not table.db and not table.catalog and table_name in cte_names:
                continue

            if table.db or table.catalog:
                table_name = table.sql(dialect=self.dialect)

            if table_name not in seen:
                seen.add(table_name)
                table_names.append(table_name)

        return table_names