from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

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

        initial_state = build_initial_state(
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

        final_state = await self.graph.ainvoke(initial_state)
        await self._persist_graph_result(
            user_message_id=user_message.message_id,
            assistant_message_id=assistant_message.message_id,
            state=final_state,
        )

        return ChatRunResult(
            conversation_id=conversation.conversation_id,
            message_id=user_message.message_id,
            assistant_message_id=assistant_message.message_id,
            state=final_state,
            response=final_state.get("response"),
            rag_references=final_state.get("rag_references") or [],
            clarification_events=final_state.get("clarification_events") or [],
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

        response = state.get("response")
        if response is not None:
            await self.message_service.update_content(
                assistant_message_id,
                response,
            )


def _normalize_query(query: str) -> str:
    normalized = (query or "").strip()
    if not normalized:
        raise ValueError("消息内容不能为空")
    return normalized
