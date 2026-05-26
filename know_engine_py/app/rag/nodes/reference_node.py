from __future__ import annotations

from collections.abc import Awaitable, Callable

from know_engine_py.app.rag.state import AgentState
from know_engine_py.app.rag.utils.reference import build_rag_references


ReferenceNode = Callable[[AgentState], Awaitable[AgentState]]


def create_reference_node() -> ReferenceNode:
    """创建引用抽取节点。

    这个节点只写入 state["rag_references"]，不直接拼 `[REFERENCE]` SSE 字符串。
    Day8 的 SSE 层会负责把 rag_references 转成前端事件。
    """

    async def reference_node(state: AgentState) -> AgentState:
        documents = state.get("selected_docs") or state.get("retrieved_docs") or []
        references = build_rag_references(
            documents,
            require_chunk_id=True,
            dedupe_by="chunkId",
        )

        return {
            **state,
            "rag_references": references,
        }

    return reference_node
