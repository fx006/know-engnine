from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    """一次文档检索允许访问的知识空间。

    这是 RAG 平台层权限契约，不绑定具体领域。
    Provider 只把它翻译成各个检索后端支持的 metadata filter。
    """

    group_id: str | None = None
    knowledge_base_id: str | None = None

    def to_metadata_filter(self) -> dict[str, str]:
        metadata_filter: dict[str, str] = {}

        if self.group_id:
            metadata_filter["groupId"] = self.group_id
        if self.knowledge_base_id:
            metadata_filter["knowledgeBaseId"] = self.knowledge_base_id

        return metadata_filter


def build_retrieval_scope(source: Mapping[str, Any]) -> RetrievalScope | None:
    """从 LangGraph state 或请求上下文中解析检索权限范围。"""
    group_id = _to_optional_string(source.get("group_id"))
    knowledge_base_id = _to_optional_string(source.get("knowledge_base_id"))

    if not group_id and not knowledge_base_id:
        return None

    return RetrievalScope(
        group_id=group_id,
        knowledge_base_id=knowledge_base_id,
    )


def _to_optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None

    return str(value)
