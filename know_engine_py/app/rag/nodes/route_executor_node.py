from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain_core.documents import Document

from know_engine_py.app.rag.state import AgentState

RouteExecutorNode = Callable[[AgentState], Awaitable[AgentState]]

_DOCUMENT_ROUTES = {"auto", "hybrid_document", "vector", "keyword"}
_TEXT_TO_SQL_ROUTES = {"text2sql", "sql", "relational_db"}
_UNSUPPORTED_ROUTES = {"text2cypher", "cypher", "graph_db"}


def create_route_executor_node(
    *,
    document_retriever_provider: Any,
    text_to_sql_retriever_provider: Any | None = None,
) -> RouteExecutorNode:
    """创建多检索通道执行节点。

    第一阶段只分发文档检索和 Text-to-SQL。
    后续 Text-to-Cypher、多路并发和融合排序都应该继续扩展这个节点，而不是塞回 retrieve_node。
    """

    async def route_executor_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在执行检索路径...",
        ]

        documents: list[Document] = []

        try:
            for route_item in _resolve_route_items(state):
                route = _normalize_route(route_item.get("route"))
                query = _resolve_route_query(state, route_item)

                if route in _DOCUMENT_ROUTES:
                    route_documents = await _execute_document_route(
                        provider=document_retriever_provider,
                        route=route,
                        query=query,
                    )
                elif route in _TEXT_TO_SQL_ROUTES:
                    route_documents = await _execute_text_to_sql_route(
                        provider=text_to_sql_retriever_provider,
                        state=state,
                        route_item=route_item,
                        query=query,
                    )
                elif route in _UNSUPPORTED_ROUTES:
                    return _failed_state(
                        state,
                        progress_messages=progress_messages,
                        error=f"当前暂不支持检索策略：{route}",
                    )
                else:
                    return _failed_state(
                        state,
                        progress_messages=progress_messages,
                        error=f"未知检索策略：{route}",
                    )

                documents.extend(
                    _tag_documents(
                        route_documents,
                        route=route,
                        query=query,
                    )
                )

        except Exception as exc:
            return _failed_state(
                state,
                progress_messages=progress_messages,
                error=f"检索路径执行失败：{exc}",
            )

        merged_documents = _dedupe_documents(documents)

        return {
            **state,
            "retrieved_docs": merged_documents,
            "selected_docs": merged_documents,
            "progress_messages": progress_messages,
            "error": None,
        }

    return route_executor_node


def _resolve_route_items(state: AgentState) -> list[Mapping[str, Any]]:
    route_plan = state.get("route_plan") or []
    if route_plan:
        return [item for item in route_plan if isinstance(item, Mapping)]

    intent_result = state.get("intent_result") or {}
    return [
        {
            "route": state.get("route_strategy") or "auto",
            "query": state.get("transformed_query") or state["query"],
            "entities": intent_result.get("entities") or {},
        }
    ]


def _normalize_route(route: object) -> str:
    value = str(route or "auto").strip().lower()
    aliases = {
        "hybrid": "hybrid_document",
        "knowledge_base": "hybrid_document",
        "document": "hybrid_document",
        "relational_db": "text2sql",
        "sql": "text2sql",
        "graph_db": "text2cypher",
        "cypher": "text2cypher",
    }
    return aliases.get(value, value)


def _resolve_route_query(state: AgentState, route_item: Mapping[str, Any]) -> str:
    return str(
        route_item.get("query")
        or state.get("transformed_query")
        or state["query"]
    )


async def _execute_document_route(
    *,
    provider: Any,
    route: str,
    query: str,
) -> list[Document]:
    if not callable(getattr(provider, "create", None)):
        raise ValueError("document_retriever_provider 必须提供 create() 方法")

    retriever = provider.create(strategy=route)
    return await retriever.ainvoke(query)

async def _execute_text_to_sql_route(
    *,
    provider: Any | None,
    state: AgentState,
    route_item: Mapping[str, Any],
    query: str,
) -> list[Document]:
    if provider is None:
        raise ValueError("Text-to-SQL 检索器未配置")

    if not callable(getattr(provider, "create", None)):
        raise ValueError("text_to_sql_retriever_provider 必须提供 create() 方法")

    intent_result = state.get("intent_result") or {}
    raw_entities = route_item.get("entities") or intent_result.get("entities") or {}

    retriever = provider.create(
        user_id=state.get("user_id"),
        entities=_compact_entities(raw_entities),
    )
    return await retriever.ainvoke(query)


def _compact_entities(entities: Any) -> dict[str, Any]:
    if not isinstance(entities, Mapping):
        return {}

    # intent_node 会补齐缺失实体为 None；Text-to-SQL 只需要已解析实体，避免把空字段写进 SQL prompt。
    return {
        str(key): value
        for key, value in entities.items()
        if value not in (None, "")
    }


def _tag_documents(
    documents: list[Document],
    *,
    route: str,
    query: str,
) -> list[Document]:
    tagged_documents: list[Document] = []

    for document in documents:
        metadata = dict(document.metadata or {})
        metadata.setdefault("retrievalRoute", route)
        metadata.setdefault("routeQuery", query)

        tagged_documents.append(
            Document(
                id=document.id,
                page_content=document.page_content,
                metadata=metadata,
            )
        )

    return tagged_documents


def _dedupe_documents(documents: list[Document]) -> list[Document]:
    deduped: list[Document] = []
    seen: set[str] = set()

    for document in documents:
        key = _document_key(document)
        if key in seen:
            continue

        seen.add(key)
        deduped.append(document)

    return deduped


def _document_key(document: Document) -> str:
    metadata = document.metadata or {}

    for key in ("chunkId", "chunk_id", "retrievalKey", "sql"):
        value = metadata.get(key)
        if value:
            return f"{key}:{value}"

    if document.id:
        return f"id:{document.id}"

    return f"text:{document.page_content}"


def _failed_state(
    state: AgentState,
    *,
    progress_messages: list[str],
    error: str,
) -> AgentState:
    return {
        **state,
        "retrieved_docs": [],
        "selected_docs": [],
        "progress_messages": progress_messages,
        "error": error,
    }