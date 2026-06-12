from __future__ import annotations

from collections.abc import Awaitable, Callable

from know_engine_py.app.rag.state import AgentState


EvidenceGuardNode = Callable[[AgentState], Awaitable[AgentState]]

INSUFFICIENT_EVIDENCE_RESPONSE = "抱歉，当前知识库中没有足够可靠的资料回答这个问题。"


def create_evidence_guard_node(
    *,
    refusal_response: str = INSUFFICIENT_EVIDENCE_RESPONSE,
) -> EvidenceGuardNode:
    """创建证据门禁节点。

    该节点位于 grader 之后、reference/generator 之前：当检索证据为空，或
    grader 已判定资料不足且 rewrite 次数耗尽时，直接返回拒答，避免生成节点
    在弱证据上编造答案。
    """

    async def evidence_guard_node(state: AgentState) -> AgentState:
        warning = _build_evidence_warning(state)
        if warning is None:
            return {
                **state,
                "evidence_warning": None,
            }

        return {
            **state,
            "response": refusal_response,
            "rag_references": [],
            "evidence_warning": warning,
            "warning_messages": [
                *state.get("warning_messages", []),
                "当前检索证据不足，已停止生成回答。",
            ],
            "error": None,
        }

    return evidence_guard_node


def _build_evidence_warning(state: AgentState) -> dict | None:
    selected_docs = state.get("selected_docs") or []
    grade_result = state.get("grade_result") or {}

    if not selected_docs:
        return {
            "type": "INSUFFICIENT_EVIDENCE",
            "reason": "没有检索到可用于回答的参考资料",
            "missing_aspects": ["参考资料"],
        }

    if bool(grade_result.get("is_sufficient", True)):
        return None

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 0)
    if retry_count < max_retries:
        return None

    missing_aspects = grade_result.get("missing_aspects") or []
    if not isinstance(missing_aspects, list):
        missing_aspects = [str(missing_aspects)]

    return {
        "type": "INSUFFICIENT_EVIDENCE",
        "reason": str(grade_result.get("reason") or "检索资料不足"),
        "missing_aspects": [str(item) for item in missing_aspects],
    }
