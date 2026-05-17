from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from know_engine_py.app.rag.state import AgentState


class IntentRoutingService(Protocol):
    """router_node 只依赖领域配置服务的意图路由查询能力。"""

    async def get_intent_or_fallback(self, domain_id: str, intent_name: str):
        ...


RouterNode = Callable[[AgentState], Awaitable[AgentState]]


def create_router_node(domain_config_service: IntentRoutingService) -> RouterNode:
    """创建查询路由节点。

    节点读取意图配置中的 retrieval_strategy，并把配置中的旧策略名归一成
    运行时检索通道。例如 hybrid 表示文档混合检索，运行时统一为
    hybrid_document，不把 SQL/Neo4j 混进文档召回概念里。
    """

    async def router_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在规划检索路径...",
        ]

        intent_result = state.get("intent_result") or {}
        intent_name = str(intent_result.get("intent") or "")
        intent_config = await domain_config_service.get_intent_or_fallback(
            domain_id=state.get("domain_id", "automotive"),
            intent_name=intent_name,
        )

        if intent_config is None:
            return {
                **state,
                "route_strategy": None,
                "route_plan": [],
                "progress_messages": progress_messages,
                "error": f"找不到意图路由配置：{intent_name}",
            }

        try:
            route_strategy = _normalize_route_strategy(intent_config.retrieval_strategy)
        except ValueError as exc:
            return {
                **state,
                "route_strategy": None,
                "route_plan": [],
                "progress_messages": progress_messages,
                "error": str(exc),
            }

        return {
            **state,
            "route_strategy": route_strategy,
            "route_plan": _build_default_route_plan(
                route_strategy=route_strategy,
                intent_name=intent_name,
                state=state,
            ),
            "progress_messages": progress_messages,
            "error": None,
        }

    return router_node


def _normalize_route_strategy(value: str) -> str:
    """把配置层策略名归一成运行时检索通道名。"""
    strategy = (value or "").strip().lower()
    aliases = {
        "vector": "vector",
        "keyword": "keyword",
        # 兼容 Day3/Day5 已有配置。运行时更名是为了强调它只代表文档召回。
        "hybrid": "hybrid_document",
        "hybrid_document": "hybrid_document",
        "document_hybrid": "hybrid_document",
        "text2sql": "text2sql",
        "sql": "text2sql",
        "text2cypher": "text2cypher",
        "cypher": "text2cypher",
        "multi_route": "multi_route",
    }

    route_strategy = aliases.get(strategy)
    if route_strategy is None:
        raise ValueError(f"不支持的检索路由策略：{value}")

    return route_strategy


def _build_default_route_plan(
    *,
    route_strategy: str,
    intent_name: str,
    state: AgentState,
) -> list[dict]:
    """构造当前配置路由的单通道 route plan。

    未来 LLM Query Router 会直接产出多个 route item；当前先把单通道
    也包装成相同结构，避免后续从简单路由列表再迁移一次。
    """
    if route_strategy == "multi_route":
        # Day7/Day9 再接真正的多通道 LLM router；当前不伪造子路由。
        return []

    intent_result = state.get("intent_result") or {}
    return [
        {
            "route": route_strategy,
            "intent": intent_name,
            "query": state.get("transformed_query") or state["query"],
            "entities": dict(intent_result.get("entities") or {}),
        }
    ]
