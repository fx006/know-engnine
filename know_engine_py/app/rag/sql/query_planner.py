from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from know_engine_py.app.rag.sql.safety import SqlSafetyValidator


class TableMetaProvider(Protocol):
    """Text-to-SQL 只依赖表元数据读取能力，不直接依赖具体 Service 实现。"""

    async def build_database_context(self) -> str:
        ...

    async def list_allowed_table_names(self) -> list[str]:
        ...


class SqlChatModel(Protocol):
    """兼容 LangChain ChatModel 的最小协议，方便测试注入 fake model。"""

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> Any:
        ...


@dataclass(slots=True)
class TextToSqlPlan:
    """LLM 生成 SQL 后的规划结果。

    当前阶段只生成和校验 SQL，不负责真实执行数据库查询。
    """

    valid: bool
    sql: str = ""
    reason: str = ""
    tables: list[str] | None = None
    allowed_tables: list[str]|None=None
    raw_response: str = ""


class TextToSqlPlanner:
    """Text-to-SQL 查询规划器。

    它是 SQL 检索链路的前半段：生成 SQL plan + 安全校验。
    真正执行 SQL、结果格式化和 fallback 检索会在后续独立组件中完成。
    """

    def __init__(
        self,
        *,
        table_meta_provider: TableMetaProvider,
        chat_model: SqlChatModel,
        safety_validator: SqlSafetyValidator | None = None,
    ):
        self.table_meta_provider = table_meta_provider
        self.chat_model = chat_model
        self.safety_validator = safety_validator or SqlSafetyValidator()

    async def plan(
        self,
        *,
        question: str,
        user_id: str | None = None,
        entities: dict[str, Any] | None = None,
    ) -> TextToSqlPlan:
        """根据用户问题生成安全 SQL 计划。"""
        database_context = await self.table_meta_provider.build_database_context()
        allowed_tables = await self.table_meta_provider.list_allowed_table_names()

        if not database_context or not allowed_tables:
            return TextToSqlPlan(
                valid=False,
                reason="缺少可查询的表结构元数据",
                tables=[],
                allowed_tables=allowed_tables
            )

        messages = self._build_messages(
            database_context=database_context,
            question=question,
            user_id=user_id,
            entities=entities,
        )

        response = await self.chat_model.ainvoke(messages)
        raw_response = self._response_content_to_text(response)
        sql = self._extract_sql(raw_response)

        safety_result = self.safety_validator.validate(
            sql,
            allowed_tables=allowed_tables,
        )

        if not safety_result.valid:
            return TextToSqlPlan(
                valid=False,
                sql=sql,
                reason=safety_result.reason,
                tables=safety_result.tables or [],
                raw_response=raw_response,
                allowed_tables=allowed_tables
            )

        return TextToSqlPlan(
            valid=True,
            sql=sql,
            tables=safety_result.tables or [],
            raw_response=raw_response,
            allowed_tables=allowed_tables
        )

    def _build_messages(
        self,
        *,
        database_context: str,
        question: str,
        user_id: str | None,
        entities: dict[str, Any] | None,
    ) -> list[BaseMessage]:
        system_prompt = (
            "你是一个只读 Text-to-SQL 生成器。"
            "你只能根据用户问题和给定表结构生成一条 MySQL SELECT 查询。"
            "不要生成 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE 等写操作或 DDL。"
            "不要访问未提供的表。"
            "对于车型名称、版本、品牌、订单类型、订单状态等自然语言描述字段，"
            "优先使用 LIKE 或包含匹配，避免因为用户简称和数据库全称不完全一致而查不到结果。"
            "只有用户给出订单号、车牌号、VIN、ID 等精确标识时才使用等值匹配。"
            "只返回 SQL，不要解释。"
        )

        human_parts = [
            "数据库结构：",
            database_context,
            "",
            f"用户问题：{question}",
        ]

        if user_id:
            # 用户 ID 是业务上下文，放在 HumanMessage，避免污染系统角色规则。
            human_parts.append(f"当前用户 ID：{user_id}")

        if entities:
            human_parts.append("已识别实体：")
            human_parts.append(json.dumps(entities, ensure_ascii=False))

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content="\n".join(human_parts)),
        ]

    def _response_content_to_text(self, response: Any) -> str:
        content = getattr(response, "content", response)

        if isinstance(content, str):
            return content.strip()

        return str(content).strip()

    def _extract_sql(self, raw_response: str) -> str:
        """兼容纯 SQL、Markdown 代码块和少量 JSON 格式返回。"""
        content = raw_response.strip()
        if not content:
            return ""

        json_sql = self._extract_sql_from_json(content)
        if json_sql:
            return json_sql

        fenced_sql = self._extract_sql_from_code_fence(content)
        if fenced_sql:
            return fenced_sql

        return content

    def _extract_sql_from_json(self, content: str) -> str:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return ""

        if not isinstance(data, dict):
            return ""

        sql = data.get("sql")
        if isinstance(sql, str):
            return sql.strip()

        return ""

    def _extract_sql_from_code_fence(self, content: str) -> str:
        match = re.search(r"```(?:sql)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return ""

        return match.group(1).strip()
