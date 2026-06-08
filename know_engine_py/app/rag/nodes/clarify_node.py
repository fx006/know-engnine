from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from know_engine_py.app.rag.state import AgentState


class IntentPreconditionService(Protocol):
    """clarify_node 只依赖读取意图配置的能力。"""

    async def get_intent_or_fallback(self, domain_id: str, intent_name: str):
        ...


class PreconditionResolverRegistry(Protocol):
    """前置条件 resolver 注册表，后续由汽车领域白名单服务实现。"""

    async def resolve(
        self,
        resolver_name: str,
        *,
        user_id: str,
        entity_value: str | None,
        state: AgentState,
        check: dict[str, Any],
    ) -> list[dict[str, Any]]:
        ...


ClarifyNode = Callable[[AgentState], Awaitable[AgentState]]


def create_clarify_node(
    domain_config_service: IntentPreconditionService,
    resolver_registry: PreconditionResolverRegistry,
) -> ClarifyNode:
    """创建澄清节点。

    节点职责：
    1. 读取当前意图的 preconditions。
    2. 检查 intent_result.entities 是否缺少关键实体。
    3. 缺实体时调用白名单 resolver 查询候选项。
    4. 生成内部 clarification_events，Day8 再映射成 SSE 事件。

    注意：这里不直接查 car_info / my_car 表，避免 LangGraph 主链路和汽车领域强耦合。
    """

    async def clarify_node(state: AgentState) -> AgentState:
        intent_result = state.get("intent_result") or {}
        intent_name = str(intent_result.get("intent") or "")
        entities = dict(intent_result.get("entities") or {})

        intent_config = await domain_config_service.get_intent_or_fallback(
            domain_id=state.get("domain_id", "automotive"),
            intent_name=intent_name,
        )
        preconditions = getattr(intent_config, "preconditions", None) if intent_config else None
        checks = _get_checks(preconditions)

        for check in checks:
            if not _check_applies(check, state):
                continue

            entity_field = str(check.get("entity_field") or "")
            if not entity_field:
                return _with_error(state, "前置条件配置缺少 entity_field")

            entity_value = entities.get(entity_field)
            if not _is_missing(entity_value):
                continue

            resolver_name = str(check.get("resolver") or "")
            if not resolver_name:
                return _with_error(state, f"前置条件 {entity_field} 缺少 resolver")

            items = await resolver_registry.resolve(
                resolver_name,
                user_id=state["user_id"],
                entity_value=None,
                state=state,
                check=check,
            )

            if not items:
                empty_action = str(check.get("empty_action") or "skip")
                if empty_action == "warn":
                    return _with_events(
                        state,
                        [
                            {
                                "type": "WARN",
                                "message": check.get("empty_message") or "缺少必要信息",
                            }
                        ],
                    )
                if empty_action == "skip":
                    continue
                return _with_error(state, f"不支持的 empty_action：{empty_action}")

            missing_action = str(check.get("missing_action") or "card_choice")
            if missing_action == "card_choice":
                card_type = str(check.get("card_type") or "CARD_CHOICE")
                display_fields = list(check.get("display_fields") or [])
                return _with_events(
                    state,
                    [
                        {
                            "type": "CARD",
                            "message": check.get("card_message") or "请补充必要信息",
                        },
                        {
                            "type": card_type,
                            "items": _project_items(items, display_fields),
                        },
                    ],
                )

            if missing_action == "warn":
                return _with_events(
                    state,
                    [
                        {
                            "type": "WARN",
                            "message": check.get("empty_message") or "缺少必要信息",
                        }
                    ],
                )

            if missing_action == "skip":
                continue

            return _with_error(state, f"不支持的 missing_action：{missing_action}")

        return {
            **state,
            "needs_clarification": False,
            "clarification_events": [],
            "error": None,
        }

    return clarify_node


def _get_checks(preconditions: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not preconditions:
        return []
    checks = preconditions.get("checks")
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict)]


def _check_applies(check: dict[str, Any], state: AgentState) -> bool:
    """判断当前 precondition check 是否适用于这次提问。

    applies_when 是领域配置，不把汽车关键词写死在节点里；节点只提供通用的
    query_contains_any 解释能力。没有 applies_when 的旧配置保持兼容，默认适用。
    """

    applies_when = check.get("applies_when")
    if not isinstance(applies_when, dict) or not applies_when:
        return True

    query_keywords = _to_string_list(applies_when.get("query_contains_any"))
    if query_keywords and not _query_contains_any(state, query_keywords):
        return False

    return True


def _query_contains_any(state: AgentState, keywords: list[str]) -> bool:
    texts = [
        str(text).casefold()
        for text in (state.get("query"), state.get("transformed_query"))
        if text not in (None, "")
    ]
    return any(keyword.casefold() in text for text in texts for keyword in keywords)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _project_items(
    items: list[dict[str, Any]],
    display_fields: list[str],
) -> list[dict[str, Any]]:
    if not display_fields:
        return items

    return [
        {
            field: item.get(field)
            for field in display_fields
            if field in item
        }
        for item in items
    ]


def _to_string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _with_events(
    state: AgentState,
    events: list[dict[str, Any]],
) -> AgentState:
    return {
        **state,
        "needs_clarification": True,
        "clarification_events": events,
        "error": None,
    }


def _with_error(state: AgentState, message: str) -> AgentState:
    return {
        **state,
        "needs_clarification": False,
        "clarification_events": [],
        "error": message,
    }
