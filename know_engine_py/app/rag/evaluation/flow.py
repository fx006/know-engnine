from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from know_engine_py.app.rag.evaluation.models import (
    EvalCase,
    FlowEvalResult,
    FlowEvalSummary,
)


def evaluate_flow(case: EvalCase, state: Mapping[str, Any]) -> FlowEvalResult:
    """评估单条样例是否走到了预期的 LangGraph 链路。

    retrieval evidence 评估只回答“证据有没有命中”；flow 评估回答“样例是否
    应该进入检索、澄清或普通聊天”。这两层分开，避免把澄清卡片误算成检索失败。
    """

    expected_flow = case.expectation.expected_flow
    actual_flow = detect_actual_flow(state)
    failures: list[str] = []
    if actual_flow != expected_flow:
        failures.append(
            f"预期进入 {expected_flow} 链路，实际进入 {actual_flow} 链路"
        )

    return FlowEvalResult(
        case_id=case.case_id,
        query=case.query,
        expected_flow=expected_flow,
        actual_flow=actual_flow,
        hit=not failures,
        failures=failures,
    )


def summarize_flow_results(results: Sequence[FlowEvalResult]) -> FlowEvalSummary:
    """汇总链路走向评测结果。"""

    result_list = list(results)
    total = len(result_list)
    hits = sum(1 for result in result_list if result.hit)
    misses = total - hits
    return FlowEvalSummary(
        total=total,
        hits=hits,
        misses=misses,
        hit_rate=hits / total if total else 0.0,
        results=result_list,
    )


def detect_actual_flow(state: Mapping[str, Any]) -> str:
    """从 LangGraph final_state 推断实际链路类型。"""

    if state.get("needs_clarification") or state.get("clarification_events"):
        return "clarification"

    if state.get("route_plan"):
        return "retrieval"

    if state.get("is_related") is False:
        return "common_chat"

    response = state.get("response")
    if isinstance(response, str) and response.strip():
        return "common_chat"

    if state.get("error"):
        return "error"

    return "unknown"
