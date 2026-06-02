from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.chat_sse import (
    clarification_events,
    done_event,
    progress_event,
    reference_event,
    token_event,
)
from know_engine_py.app.api.dependencies.auth import get_optional_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.rag.chat_graph_builder import build_chat_rag_graph_from_db
from know_engine_py.app.schemas.chat import (
    ChatConversationResponse,
    ChatMessageResponse,
    ChatSendRequest,
)
from know_engine_py.app.services.chat_application_service import (
    ChatApplicationService,
    ChatRunResult,
    RagGraph,
)
from know_engine_py.app.services.chat_conversation_service import (
    ChatConversationService,
)
from know_engine_py.app.services.chat_memory_service import ChatMemoryService
from know_engine_py.app.services.chat_message_service import ChatMessageService
from know_engine_py.app.services.access_control_service import AccessControlService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/send")
async def send_chat(
    request: ChatSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_optional_current_user),
):
    """发送聊天消息，返回 SSE 流。

    当前阶段先执行完整 LangGraph，再把结果包装成 SSE 帧。
    这样可以避免 StreamingResponse 已经开始后再抛 HTTPException。
    token 级实时流式输出后续再接 graph.astream / astream_events。
    """
    normalized_user_id = _resolve_user_id(
        request_user_id=request.user_id,
        current_user=current_user,
    )
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="userId 不能为空")

    normalized_content = (request.content or "").strip()
    if not normalized_content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    graph = _get_rag_graph(db)
    access_control_service = AccessControlService(db)
    group_id, knowledge_base_id = await _resolve_conversation_scope(
        request=request,
        current_user=current_user,
        access_control_service=access_control_service,
    )
    service = _build_chat_application_service(db, graph)

    try:
        result = await service.run_chat(
            user_id=normalized_user_id,
            query=normalized_content,
            conversation_id=request.conversation_id,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await db.rollback()
        raise

    async def event_stream() -> AsyncGenerator[str, None]:
        yield progress_event("正在处理您的问题...")

        for frame in _result_to_sse_frames(result):
            yield frame

        yield done_event(result.conversation_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@router.get("/list", response_model=list[ChatConversationResponse])
async def list_conversations(
    user_id: str | None = Query(default=None, alias="userId"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_optional_current_user),
):
    """查询当前用户的会话列表。"""
    normalized_user_id = _resolve_user_id(
        request_user_id=user_id,
        current_user=current_user,
    )
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="userId 不能为空")

    service = ChatConversationService(db)
    return await service.list_conversations(normalized_user_id)


@router.get("/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    conversation_id: str = Query(..., alias="conversationId"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_optional_current_user),
):
    """查询指定会话下的全部消息。"""
    normalized_conversation_id = (conversation_id or "").strip()
    if not normalized_conversation_id:
        raise HTTPException(status_code=400, detail="conversationId 不能为空")

    conversation_service = ChatConversationService(db)
    conversation = await conversation_service.get_by_conversation_id(
        normalized_conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在或已删除")
    if current_user is not None and conversation.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="不能访问其他用户的会话")

    message_service = ChatMessageService(db)
    return await message_service.get_messages_by_conversation_id(
        normalized_conversation_id
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_optional_current_user),
):
    """删除会话及其消息。"""
    normalized_conversation_id = (conversation_id or "").strip()
    if not normalized_conversation_id:
        raise HTTPException(status_code=400, detail="conversationId 不能为空")

    conversation_service = ChatConversationService(db)
    message_service = ChatMessageService(db)

    try:
        conversation = await conversation_service.get_by_conversation_id(
            normalized_conversation_id
        )
        if conversation is None:
            raise ValueError("会话不存在或已删除")
        if current_user is not None and conversation.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="不能删除其他用户的会话")

        await message_service.delete_messages_by_conversation_id(
            normalized_conversation_id
        )
        await conversation_service.delete_conversation(normalized_conversation_id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        await db.rollback()
        raise

    return {"success": True}


def _build_chat_application_service(
    db: AsyncSession,
    graph: RagGraph,
) -> ChatApplicationService:
    """组装聊天应用服务依赖。"""
    conversation_service = ChatConversationService(db)
    message_service = ChatMessageService(db)
    memory_service = ChatMemoryService(message_service)

    return ChatApplicationService(
        conversation_service=conversation_service,
        message_service=message_service,
        memory_service=memory_service,
        graph=graph,
    )


async def _resolve_conversation_scope(
    *,
    request: ChatSendRequest,
    current_user: UserModel | None,
    access_control_service: AccessControlService,
) -> tuple[str | None, str | None]:
    """把请求里的 knowledgeBaseId 解析成会话级群组/知识库范围。"""
    knowledge_base_id = (request.knowledge_base_id or "").strip() or None
    if not knowledge_base_id:
        return None, None

    knowledge_base = await access_control_service.get_knowledge_base(knowledge_base_id)
    if knowledge_base is None or knowledge_base.status != "active":
        raise HTTPException(status_code=404, detail="知识库不存在或已失效")

    if current_user is not None and not await access_control_service.is_group_member(
        group_id=knowledge_base.group_id,
        user_id=current_user.user_id,
    ):
        raise HTTPException(status_code=403, detail="当前用户无权使用该知识库")

    return knowledge_base.group_id, knowledge_base.knowledge_base_id


def _result_to_sse_frames(result: ChatRunResult) -> list[str]:
    """把应用层结果转成 SSE 帧。"""
    frames: list[str] = []

    frames.extend(_progress_frames(result))

    if result.clarification_events:
        frames.extend(clarification_events(result.clarification_events))
        return frames

    if result.response:
        frames.append(token_event(result.response))

    if result.rag_references:
        frames.append(reference_event(result.rag_references))

    return frames


def _progress_frames(result: ChatRunResult) -> list[str]:
    """把 LangGraph state 中的进度消息转成 SSE 帧。"""
    frames: list[str] = []

    for message in result.state.get("progress_messages") or []:
        normalized_message = _normalize_progress_message(message)
        if normalized_message:
            frames.append(progress_event(normalized_message))

    return frames


def _normalize_progress_message(message: object) -> str:
    """兼容 node 内部已经带 [PROGRESS]: 前缀的消息。"""
    normalized = str(message or "").strip()
    if normalized.startswith("[PROGRESS]:"):
        return normalized.removeprefix("[PROGRESS]:").strip()
    return normalized


def _resolve_user_id(
    *,
    request_user_id: str | None,
    current_user: UserModel | None,
) -> str:
    """解析接口使用的 user_id。

    登录态优先，旧参数兜底；这样能兼容旧调用方，又避免已登录用户伪造 userId。
    """
    if current_user is not None:
        requested = (request_user_id or "").strip()
        if requested and requested != current_user.user_id:
            raise HTTPException(status_code=403, detail="不能操作其他用户的数据")
        return current_user.user_id

    return (request_user_id or "").strip()


def _get_rag_graph(db: AsyncSession) -> RagGraph:
    """获取真实 LangGraph 实例。

    这里只调用图装配入口，不在 Router 中直接创建 PromptService、
    ChatModelFactory、DocumentRetrieverProvider 等细节对象。
    """
    return build_chat_rag_graph_from_db(db=db)
