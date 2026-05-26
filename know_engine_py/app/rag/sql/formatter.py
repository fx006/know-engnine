from __future__ import annotations

from typing import Any

from know_engine_py.app.rag.sql.executor import SqlExecutionResult


class SqlResultFormatter:
    """把 SQL 执行结果格式化为 RAG 可注入上下文。

    SQL 查询返回的是结构化 rows；generator_node 需要的是可读文本。
    这个类只做展示/上下文化，不负责执行 SQL，也不负责安全校验。
    """

    def __init__(self, *, max_cell_length: int = 200):
        if max_cell_length <= 0:
            raise ValueError("max_cell_length 必须大于 0")

        self.max_cell_length = max_cell_length

    def format(self, result: SqlExecutionResult) -> str:
        """把 SQL 执行结果转换成给 LLM 使用的参考资料文本。"""
        if not result.success:
            return self._format_failure(result)

        if not result.rows:
            return self._format_empty_result(result)

        lines = [
            "结构化查询结果：",
            f"执行 SQL：{result.executed_sql or result.sql}",
        ]

        if result.tables:
            lines.append(f"涉及表：{', '.join(result.tables)}")

        lines.append("")

        for index, row in enumerate(result.rows, start=1):
            lines.append(f"第 {index} 行：")
            for column in result.columns:
                lines.append(f"- {column}: {self._format_value(row.get(column))}")
            lines.append("")

        if result.truncated:
            lines.append("提示：结果已按最大行数截断，仅展示部分数据。")

        return "\n".join(lines).strip()

    def _format_failure(self, result: SqlExecutionResult) -> str:
        return f"结构化查询失败：{result.error or '未知错误'}"

    def _format_empty_result(self, result: SqlExecutionResult) -> str:
        lines = [
            "结构化查询结果：未查询到匹配数据。",
            f"执行 SQL：{result.executed_sql or result.sql}",
        ]

        if result.tables:
            lines.append(f"涉及表：{', '.join(result.tables)}")

        return "\n".join(lines)

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "NULL"

        text = str(value)
        if len(text) <= self.max_cell_length:
            return text

        return f"{text[: self.max_cell_length]}..."