from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from know_engine_py.app.rag.state import AgentState, build_initial_state
from know_engine_py.app.services.chat_conversation_service import (
    ChatConversationService,
)
from know_engine_py.app.services.chat_memory_service import ChatMemoryService
from know_engine_py.app.services.chat_message_service import ChatMessageService


class RagGraph(Protocol):
    """LangGraph 编译结果协议，只依赖 ainvoke，方便测试时注入 fake graph。"""

    async def ainvoke(self, input: AgentState) -> AgentState:
        ...


@dataclass(slots=True)
class ChatRunResult:
    """一次聊天执行后的应用层结果。"""

    conversation_id: str
    message_id: str
    assistant_message_id: str
    state: AgentState
    response: str | None
    rag_references: list[dict[str, Any]]
    clarification_events: list[dict[str, Any]]


@dataclass(slots=True)
class ChatStreamEvent:
    """应用层聊天流事件。

    Router 负责把这些事件映射成 SSE frame；Service 只表达业务语义。
    """

    kind: Literal["progress", "warning", "answer_delta", "result"]
    message: str | None = None
    result: ChatRunResult | None = None


class ChatApplicationService:
    """聊天应用编排服务。

    负责会话准备、消息落库、短期记忆加载、调用 LangGraph、回写图执行结果。
    这里不直接处理 HTTP/SSE，避免 API 层和业务编排层耦合。
    """

    def __init__(
        self,
        *,
        conversation_service: ChatConversationService,
        message_service: ChatMessageService,
        memory_service: ChatMemoryService,
        graph: RagGraph,
        domain_id: str = "automotive",
    ):
        self.conversation_service = conversation_service
        self.message_service = message_service
        self.memory_service = memory_service
        self.graph = graph
        self.domain_id = domain_id

    async def run_chat(
        self,
        *,
        user_id: str,
        query: str,
        conversation_id: str | None = None,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
    ) -> ChatRunResult:
        """执行一次完整聊天。

        当前是非 SSE 的应用编排版本；后续 SSE 层会基于同一套服务拆出事件流。
        """
        initial_state = await self._prepare_initial_state(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
        )

        final_state = await self.graph.ainvoke(initial_state)
        await self._persist_graph_result(
            user_message_id=initial_state["message_id"],
            assistant_message_id=initial_state["assistant_message_id"],
            state=final_state,
        )

        return _build_run_result(final_state)

    async def stream_chat(
        self,
        *,
        user_id: str,
        query: str,
        conversation_id: str | None = None,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
    ) -> AsyncIterator[ChatStreamEvent]:
        """执行一次聊天，并尽量输出 LangGraph 节点级进度事件。

        当前同时消费 LangGraph updates 与 custom stream：
        - updates 用于节点级 progress/warning；
        - custom 用于 generator 写出的 answer_delta。
        最终仍聚合完整 state 后统一回写消息表。
        """
        initial_state = await self._prepare_initial_state(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
        )

        final_state = dict(initial_state)
        seen_progress: set[str] = set()
        seen_warnings: set[str] = set()

        if hasattr(self.graph, "astream"):
            async for chunk in self.graph.astream(
                initial_state,
                stream_mode=["updates", "custom"],
            ):
                stream_mode, payload = _split_stream_chunk(chunk)

                if stream_mode == "custom":
                    answer_delta = _extract_answer_delta(payload)
                    if answer_delta:
                        yield ChatStreamEvent(
                            kind="answer_delta",
                            message=answer_delta,
                        )
                    continue

                for state_update in _extract_state_updates(payload):
                    final_state.update(state_update)

                for message in _new_progress_messages(final_state, seen_progress):
                    yield ChatStreamEvent(kind="progress", message=message)

                for message in _new_warning_messages(final_state, seen_warnings):
                    yield ChatStreamEvent(kind="warning", message=message)
        else:
            final_state = await self.graph.ainvoke(initial_state)
            for message in _new_progress_messages(final_state, seen_progress):
                yield ChatStreamEvent(kind="progress", message=message)
            for message in _new_warning_messages(final_state, seen_warnings):
                yield ChatStreamEvent(kind="warning", message=message)

        await self._persist_graph_result(
            user_message_id=initial_state["message_id"],
            assistant_message_id=initial_state["assistant_message_id"],
            state=final_state,
        )

        yield ChatStreamEvent(
            kind="result",
            result=_build_run_result(final_state),
        )

    async def _persist_graph_result(
        self,
        *,
        user_message_id: str,
        assistant_message_id: str,
        state: AgentState,
    ) -> None:
        """把 LangGraph 结果回写到消息表。"""
        transformed_query = state.get("transformed_query")
        if transformed_query:
            await self.message_service.update_transform_content(
                user_message_id,
                transformed_query,
            )

        rag_references = state.get("rag_references") or []
        if rag_references:
            await self.message_service.update_rag_references(
                assistant_message_id,
                rag_references,
            )

        clarification_events = state.get("clarification_events") or []
        if clarification_events:
            await self.message_service.update_extra_metadata(
                assistant_message_id,
                {
                    "needsClarification": True,
                    "clarificationEvents": clarification_events,
                },
            )

        response = state.get("response")
        if response is not None:
            await self.message_service.update_content(
                assistant_message_id,
                response,
            )

    async def _prepare_initial_state(
        self,
        *,
        user_id: str,
        query: str,
        conversation_id: str | None,
        group_id: str | None,
        knowledge_base_id: str | None,
    ) -> AgentState:
        normalized_query = _normalize_query(query)

        conversation = await self.conversation_service.ensure_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            first_message=normalized_query,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
        )

        user_message = await self.message_service.save_user_message(
            conversation_id=conversation.conversation_id,
            content=normalized_query,
        )
        assistant_message = await self.message_service.save_assistant_message(
            conversation_id=conversation.conversation_id,
        )

        # 新一轮消息写入后清缓存，确保短期记忆从 DB 重新加载。
        await self.memory_service.evict_cache(conversation.conversation_id)
        chat_history = await self.memory_service.load_recent_chat_history(
            conversation.conversation_id
        )

        return build_initial_state(
            query=normalized_query,
            user_id=user_id,
            domain_id=self.domain_id,
            group_id=conversation.group_id,
            knowledge_base_id=conversation.knowledge_base_id,
            conversation_id=conversation.conversation_id,
            message_id=user_message.message_id,
            assistant_message_id=assistant_message.message_id,
            chat_history=chat_history,
        )


def _normalize_query(query: str) -> str:
    normalized = (query or "").strip()
    if not normalized:
        raise ValueError("消息内容不能为空")
    return normalized


def _build_run_result(state: AgentState) -> ChatRunResult:
    return ChatRunResult(
        conversation_id=str(state.get("conversation_id") or ""),
        message_id=str(state.get("message_id") or ""),
        assistant_message_id=str(state.get("assistant_message_id") or ""),
        state=state,
        response=state.get("response"),
        rag_references=state.get("rag_references") or [],
        clarification_events=state.get("clarification_events") or [],
    )


def _extract_state_updates(update: Any) -> list[dict[str, Any]]:
    if not isinstance(update, dict):
        return []

    if _looks_like_state_update(update):
        return [update]

    updates: list[dict[str, Any]] = []
    for value in update.values():
        if isinstance(value, dict):
            updates.append(value)
    return updates


def _looks_like_state_update(update: dict[str, Any]) -> bool:
    state_keys = {
        "progress_messages",
        "warning_messages",
        "response",
        "rag_references",
        "clarification_events",
        "error",
    }
    return any(key in update for key in state_keys)


def _split_stream_chunk(chunk: Any) -> tuple[str, Any]:
    """兼容 LangGraph 单 stream_mode 与多 stream_mode 的输出形态。"""
    if (
        isinstance(chunk, tuple)
        and len(chunk) == 2
        and chunk[0] in {"updates", "custom"}
    ):
        return str(chunk[0]), chunk[1]

    return "updates", chunk


def _extract_answer_delta(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "answer_delta":
        return None

    content = str(payload.get("content") or "")
    return content or None


def _new_progress_messages(
    state: dict[str, Any],
    seen: set[str],
) -> list[str]:
    messages: list[str] = []
    for message in state.get("progress_messages") or []:
        if str(message or "").strip().startswith("[WARN]:"):
            continue
        normalized = _normalize_prefixed_message(message, "[PROGRESS]:")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(normalized)
    return messages


def _new_warning_messages(
    state: dict[str, Any],
    seen: set[str],
) -> list[str]:
    messages: list[str] = []
    for message in state.get("warning_messages") or []:
        normalized = str(message or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(normalized)

    for message in state.get("progress_messages") or []:
        normalized = str(message or "").strip()
        if not normalized.startswith("[WARN]:"):
            continue
        normalized = normalized.removeprefix("[WARN]:").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        messages.append(normalized)

    evidence_warning = state.get("evidence_warning")
    if evidence_warning and not messages:
        normalized = str(evidence_warning.get("reason") or "当前检索证据不足")
        if normalized and normalized not in seen:
            seen.add(normalized)
            messages.append(normalized)
    return messages


def _normalize_prefixed_message(message: object, prefix: str) -> str:
    normalized = str(message or "").strip()
    if normalized.startswith(prefix):
        return normalized.removeprefix(prefix).strip()
    return normalized
