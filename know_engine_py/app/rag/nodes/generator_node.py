from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langgraph.config import get_stream_writer

from know_engine_py.app.rag.nodes.message_history import build_chat_messages
from know_engine_py.app.rag.state import AgentState


class GeneratorPromptService(Protocol):
    """generator_node 只依赖 PromptService 的指定 Prompt 查询能力。"""

    async def get_prompt(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> str | None:
        ...


GeneratorNode = Callable[[AgentState], Awaitable[AgentState]]


def create_generator_node(
    prompt_service: GeneratorPromptService,
    chat_model: BaseChatModel,
) -> GeneratorNode:
    """创建回答生成节点。

    系统 Prompt 只放角色和回答规则；当前问题与参考资料放 HumanMessage，
    避免把每轮动态变量写进系统 Prompt。
    """

    async def generator_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在生成回答...",
        ]

        intent_result = state.get("intent_result") or {}
        intent_name = str(intent_result.get("intent") or "")
        prompt = await prompt_service.get_prompt(
            domain_id=state.get("domain_id", "automotive"),
            intent_name=intent_name,
            prompt_type="chat",
        )

        if not prompt:
            return {
                **state,
                "response": None,
                "progress_messages": progress_messages,
                "error": f"缺少 {intent_name} 的 chat Prompt",
            }

        docs = state.get("selected_docs") or state.get("retrieved_docs") or []
        messages = build_chat_messages(
            system_prompt=prompt,
            chat_history=state.get("chat_history"),
            current_user_message=_build_user_message(
                query=state["query"],
                documents=docs,
            ),
        )
        response_content = await _generate_response_content(chat_model, messages)

        return {
            **state,
            "system_prompt": prompt,
            "response": response_content,
            "progress_messages": progress_messages,
            "error": None,
        }

    return generator_node


def _build_user_message(query: str, documents: list[Document]) -> str:
    """把检索上下文和当前问题放入 HumanMessage。"""
    context = "\n\n".join(document.page_content for document in documents)
    if not context:
        context = "暂无可用参考资料。"

    return (
        "回答边界：\n"
        "- 只依据参考资料回答用户问题。\n"
        "- 禁止补充参考资料未提供的额外建议、行动指引或事实判断。\n"
        "- 不要添加营销话术、免责声明或主动追问。\n"
        "- 如果参考资料只支持一个事实，只回答该事实。\n\n"
        f"参考资料：\n{context}\n\n"
        f"用户问题：\n{query}"
    )


async def _generate_response_content(
    chat_model: BaseChatModel,
    messages: list[Any],
) -> str:
    """调用生成模型；在 LangGraph streaming 上下文中同步发 answer_delta。"""
    stream_writer = _get_optional_stream_writer()
    if stream_writer is not None and hasattr(chat_model, "astream"):
        chunks: list[str] = []
        async for chunk in chat_model.astream(messages):
            content = _content_to_text(getattr(chunk, "content", ""))
            if not content:
                continue
            chunks.append(content)
            stream_writer({"type": "answer_delta", "content": content})
        return "".join(chunks).strip()

    response = await chat_model.ainvoke(messages)
    return _content_to_text(getattr(response, "content", "")).strip()


def _get_optional_stream_writer():
    try:
        return get_stream_writer()
    except RuntimeError:
        return None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content or "")
