from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from know_engine_py.app.rag.nodes.message_history import build_chat_messages
from know_engine_py.app.rag.state import AgentState


class GraderPromptService(Protocol):
    """grader_node 只依赖 PromptService 的指定 Prompt 查询能力。"""

    async def get_prompt(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> str | None:
        ...


GraderNode = Callable[[AgentState], Awaitable[AgentState]]


def create_grader_node(
    prompt_service: GraderPromptService,
    chat_model: BaseChatModel,
) -> GraderNode:
    """创建检索结果质量评估节点。"""

    async def grader_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在评估检索结果...",
        ]
        documents = state.get("selected_docs") or []

        if not documents:
            grade_result = {
                "is_sufficient": False,
                "reason": "没有检索到可用于回答的参考资料",
                "missing_aspects": ["参考资料"],
                "confidence": 1.0,
            }
            return {
                **state,
                "grade_result": grade_result,
                "needs_rewrite": True,
                "progress_messages": progress_messages,
                "error": None,
            }

        prompt = await prompt_service.get_prompt(
            domain_id=state.get("domain_id", "automotive"),
            intent_name="_system_",
            prompt_type="retrieval_grader",
        )

        if not prompt:
            return {
                **state,
                "grade_result": None,
                "needs_rewrite": False,
                "progress_messages": progress_messages,
                "error": "缺少 retrieval_grader Prompt",
            }

        response = await chat_model.ainvoke(
            build_chat_messages(
                system_prompt=prompt,
                chat_history=state.get("chat_history"),
                current_user_message=_build_user_message(
                    query=state["query"],
                    retrieval_query=state.get("transformed_query"),
                    documents=documents,
                ),
            )
        )

        try:
            grade_result = _parse_grade_result(str(response.content))
        except ValueError as exc:
            # 评估失败时不阻塞主链路，保守地继续生成，避免进入无效 rewrite 循环。
            grade_result = {
                "is_sufficient": True,
                "reason": f"检索结果评估解析失败，已降级使用现有资料：{exc}",
                "missing_aspects": [],
                "confidence": 0.0,
                "raw_output": str(response.content),
            }

        return {
            **state,
            "grade_result": grade_result,
            "needs_rewrite": not bool(grade_result["is_sufficient"]),
            "progress_messages": progress_messages,
            "error": None,
        }

    return grader_node


def _build_user_message(
    *,
    query: str,
    retrieval_query: str | None,
    documents: list[Document],
) -> str:
    """构造给 grader LLM 的动态输入。"""
    context = "\n\n".join(
        _format_document(index=index, document=document)
        for index, document in enumerate(documents, start=1)
    )

    retrieval_query_text = retrieval_query or query

    return (
        f"用户原问题：\n{query}\n\n"
        f"实际检索查询：\n{retrieval_query_text}\n\n"
        f"候选参考资料：\n{context}\n\n"
        "请判断这些参考资料是否足以回答用户原问题。"
    )


def _format_document(index: int, document: Document) -> str:
    metadata = document.metadata or {}
    chunk_id = metadata.get("chunkId") or metadata.get("chunk_id") or ""
    title = (
        metadata.get("fileName")
        or metadata.get("documentTitle")
        or metadata.get("title")
        or ""
    )

    return (
        f"[{index}] title={title} chunkId={chunk_id}\n"
        f"{document.page_content}"
    )


def _parse_grade_result(content: str) -> dict[str, Any]:
    payload = _strip_json_code_fence(content)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型未返回合法 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("模型返回结果不是 JSON 对象")

    return _normalize_grade_result(data)


def _strip_json_code_fence(content: str) -> str:
    text = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _normalize_grade_result(data: dict[str, Any]) -> dict[str, Any]:
    is_sufficient = _to_bool(data.get("is_sufficient"))
    missing_aspects = data.get("missing_aspects") or []

    if not isinstance(missing_aspects, list):
        missing_aspects = [str(missing_aspects)]

    return {
        "is_sufficient": is_sufficient,
        "reason": str(data.get("reason") or ""),
        "missing_aspects": [str(item) for item in missing_aspects],
        "confidence": _to_float(data.get("confidence")),
    }


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "是", "足够"}

    return bool(value)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None