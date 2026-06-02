from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, Mapping, Protocol, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from know_engine_py.app.rag.state import AgentState


class IntentRoutingService(Protocol):
    """router_node 只依赖领域配置服务的意图路由查询能力。"""

    async def get_intent_or_fallback(self, domain_id: str, intent_name: str):
        ...


RouterNode = Callable[[AgentState], Awaitable[AgentState]]

DEFAULT_ALLOWED_ROUTE_STRATEGIES = (
    "hybrid_document",
    "vector",
    "keyword",
    "text2sql",
)


def create_router_node(
    domain_config_service: IntentRoutingService,
    query_router_model: Any | None = None,
    *,
    allowed_route_strategies: Sequence[str] | None = None,
) -> RouterNode:
    """创建查询路由节点。

    有 query_router_model 时，优先让 LLM 在白名单范围内生成 route_plan；
    没有模型、模型输出非法或调用失败时，回退到意图配置 retrieval_strategy。
    retrieval_strategy 因此是稳定 fallback，不再代表最终智能路由能力。
    """
    allowed_routes = tuple(
        _normalize_route_strategy(route)
        for route in (allowed_route_strategies or DEFAULT_ALLOWED_ROUTE_STRATEGIES)
    )

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

        fallback_plan = _build_default_route_plan(
            route_strategy=route_strategy,
            intent_name=intent_name,
            state=state,
        )

        if query_router_model is not None:
            llm_result = await _try_build_llm_route_plan(
                model=query_router_model,
                state=state,
                fallback_route_strategy=route_strategy,
                fallback_route_plan=fallback_plan,
                intent_name=intent_name,
                allowed_routes=allowed_routes,
            )
            return {
                **state,
                "route_strategy": llm_result["route_strategy"],
                "route_plan": llm_result["route_plan"],
                "route_planner_source": llm_result["source"],
                "route_planner_error": llm_result.get("error"),
                "progress_messages": progress_messages,
                "error": None,
            }

        return {
            **state,
            "route_strategy": route_strategy,
            "route_plan": fallback_plan,
            "route_planner_source": "config_fallback",
            "route_planner_error": None,
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


async def _try_build_llm_route_plan(
    *,
    model: Any,
    state: AgentState,
    fallback_route_strategy: str,
    fallback_route_plan: list[dict],
    intent_name: str,
    allowed_routes: Sequence[str],
) -> dict[str, Any]:
    """调用 LLM 生成 route_plan；失败时返回配置 fallback。"""
    try:
        response = await model.ainvoke(
            _build_query_router_messages(
                state=state,
                fallback_route_strategy=fallback_route_strategy,
                intent_name=intent_name,
                allowed_routes=allowed_routes,
            )
        )
        raw_text = _response_content_to_text(response)
        route_plan = _parse_and_validate_route_plan(
            raw_text,
            state=state,
            intent_name=intent_name,
            allowed_routes=allowed_routes,
        )
    except Exception as exc:
        return _fallback_route_result(
            fallback_route_strategy=fallback_route_strategy,
            fallback_route_plan=fallback_route_plan,
            reason=f"LLM 路由规划失败：{exc}",
        )

    if not route_plan:
        return _fallback_route_result(
            fallback_route_strategy=fallback_route_strategy,
            fallback_route_plan=fallback_route_plan,
            reason="LLM 路由规划结果为空",
        )

    return {
        "source": "llm",
        "route_strategy": _resolve_route_strategy_from_plan(route_plan),
        "route_plan": route_plan,
        "error": None,
    }


def _build_query_router_messages(
    *,
    state: AgentState,
    fallback_route_strategy: str,
    intent_name: str,
    allowed_routes: Sequence[str],
) -> list[BaseMessage]:
    intent_result = state.get("intent_result") or {}
    entities = intent_result.get("entities") or {}

    system_prompt = (
        "你是 Know Engine 的检索路由规划器。"
        "你的任务是根据用户问题选择一个或多个检索通道，并输出 JSON。"
        "只能使用 allowed_route_strategies 中列出的 route。"
        "hybrid_document 用于知识库文档、政策、说明、FAQ、维修保养规则。"
        "text2sql 用于业务表数据，例如订单、金额、名下车辆、车型指导价、状态、日期和统计。"
        "vector 和 keyword 仅在明确需要单独语义向量或关键词检索时使用；一般文档问题优先 hybrid_document。"
        "如果一个问题同时需要文档规则和业务数据，输出多个 route item。"
        "只返回 JSON，不要解释。"
    )

    payload = {
        "allowed_route_strategies": list(allowed_routes),
        "fallback_route_strategy": fallback_route_strategy,
        "query": state["query"],
        "transformed_query": state.get("transformed_query"),
        "intent": intent_name,
        "entities": entities,
        "chat_history": state.get("chat_history", [])[-6:],
        "knowledge_scope": {
            "group_id": state.get("group_id"),
            "knowledge_base_id": state.get("knowledge_base_id"),
        },
        "output_schema": {
            "route_plan": [
                {
                    "route": "hybrid_document | text2sql | vector | keyword",
                    "query": "给该检索通道使用的子问题",
                    "intent": "本 route 对应的业务意图",
                    "entities": {"key": "value"},
                    "reason": "选择该通道的简短原因",
                }
            ]
        },
    }

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
    ]


def _response_content_to_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def _parse_and_validate_route_plan(
    raw_text: str,
    *,
    state: AgentState,
    intent_name: str,
    allowed_routes: Sequence[str],
) -> list[dict[str, Any]]:
    payload = _extract_json_payload(raw_text)
    route_items = payload.get("route_plan")

    if not isinstance(route_items, list):
        raise ValueError("LLM route_plan 必须是数组")

    route_plan: list[dict[str, Any]] = []
    for item in route_items[:3]:
        if not isinstance(item, Mapping):
            continue

        route = _normalize_route_strategy(str(item.get("route") or ""))
        if route not in allowed_routes:
            raise ValueError(f"LLM 生成了未授权 route：{route}")

        query = str(
            item.get("query")
            or state.get("transformed_query")
            or state["query"]
        ).strip()
        if not query:
            continue

        route_plan.append(
            {
                "route": route,
                "intent": str(item.get("intent") or intent_name),
                "query": query,
                "entities": _resolve_route_entities(item, state),
                "reason": str(item.get("reason") or ""),
            }
        )

    return route_plan


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    content = raw_text.strip()
    if not content:
        raise ValueError("LLM 路由响应为空")

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if fenced_match:
        content = fenced_match.group(1).strip()

    payload = json.loads(content)
    if isinstance(payload, list):
        return {"route_plan": payload}
    if isinstance(payload, dict):
        return payload

    raise ValueError("LLM 路由响应必须是 JSON object 或 array")


def _resolve_route_entities(
    item: Mapping[str, Any],
    state: AgentState,
) -> dict[str, Any]:
    if isinstance(item.get("entities"), Mapping):
        return dict(item["entities"])

    intent_result = state.get("intent_result") or {}
    entities = intent_result.get("entities") or {}
    if isinstance(entities, Mapping):
        return dict(entities)

    return {}


def _resolve_route_strategy_from_plan(route_plan: list[dict[str, Any]]) -> str:
    if len(route_plan) > 1:
        return "multi_route"
    return str(route_plan[0]["route"])


def _fallback_route_result(
    *,
    fallback_route_strategy: str,
    fallback_route_plan: list[dict],
    reason: str,
) -> dict[str, Any]:
    return {
        "source": "config_fallback",
        "route_strategy": fallback_route_strategy,
        "route_plan": fallback_route_plan,
        "error": reason,
    }
