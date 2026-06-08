from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from know_engine_py.app.rag.evaluation.ragas_adapter import RagasTextScores
from know_engine_py.app.rag.evaluation.runner import EvaluationRunSummary
from know_engine_py.app.rag.evaluation.usage import (
    EvaluationUsageEstimate,
    sum_usage_estimates,
)


def evaluation_summary_to_dict(
    summary: EvaluationRunSummary,
    *,
    ragas_scores: dict[str, RagasTextScores] | None = None,
) -> dict[str, Any]:
    """将评测汇总结果转换成可 JSON 序列化的报告结构。"""

    score_map = ragas_scores or {}
    return {
        "flow": _flow_summary_to_dict(summary.flow_summary),
        "retrieval": {
            "retrieved": _summary_to_dict(summary.retrieved_summary),
            "selected": _summary_to_dict(summary.selected_summary),
        },
        "generation": {
            "ragas": _ragas_summary_to_dict(score_map),
            "usage_estimate": _usage_estimate_to_dict(
                sum_usage_estimates(
                    [
                        score.usage_estimate
                        for score in score_map.values()
                    ]
                )
            ),
        },
        "elapsed_ms": summary.elapsed_ms,
        "cases": [
            _case_result_to_dict(
                result,
                ragas_score=score_map.get(result.case.case_id),
            )
            for result in summary.results
        ],
    }


def write_evaluation_report(
    path: str | Path,
    payload: dict[str, Any],
) -> Path:
    """写入评测报告 JSON 文件。"""

    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def _case_result_to_dict(result, *, ragas_score: RagasTextScores | None) -> dict[str, Any]:
    final_state = result.final_state or {}

    return {
        "case_id": result.case.case_id,
        "query": result.case.query,
        "reference_answer": result.case.reference_answer,
        "negative_expected": result.case.negative_expected,
        "tags": list(result.case.tags),
        "flow": _flow_result_to_dict(result.flow_result),
        "retrieval": {
            "retrieved": _eval_result_to_dict(result.retrieved_result),
            "selected": _eval_result_to_dict(result.selected_result),
        },
        "generation": {
            "response": result.response,
            "contexts": result.retrieved_contexts,
            "ragas": _ragas_score_to_dict(ragas_score),
            "usage_estimate": _usage_estimate_to_dict(
                ragas_score.usage_estimate if ragas_score else None
            ),
        },
        "trace": {
            # 评测报告必须能解释“为什么没进入检索”，否则 clarify/common 分支会被误判成召回失败。
            "is_related": final_state.get("is_related"),
            "intent_result": final_state.get("intent_result"),
            "needs_clarification": bool(final_state.get("needs_clarification", False)),
            "clarification_events": list(final_state.get("clarification_events") or []),
            "transformed_query": final_state.get("transformed_query"),
            "route_strategy": final_state.get("route_strategy"),
            "route_plan": result.route_plan,
            "route_planner_source": result.route_planner_source,
            "route_planner_error": final_state.get("route_planner_error"),
            "evidence_warning": final_state.get("evidence_warning"),
            "rag_references": list(result.rag_references),
            "progress_messages": list(final_state.get("progress_messages") or []),
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
        },
    }


def _flow_summary_to_dict(summary) -> dict[str, Any]:
    return {
        "total": summary.total,
        "hits": summary.hits,
        "misses": summary.misses,
        "hit_rate": summary.hit_rate,
    }


def _flow_result_to_dict(result) -> dict[str, Any]:
    return {
        "expected_flow": result.expected_flow,
        "actual_flow": result.actual_flow,
        "hit": result.hit,
        "failures": list(result.failures),
    }


def _summary_to_dict(summary) -> dict[str, Any]:
    return {
        "total": summary.total,
        "hits": summary.hits,
        "misses": summary.misses,
        "hit_rate": summary.hit_rate,
        "evidence": _evidence_summary_to_dict(summary.evidence_summary),
    }


def _eval_result_to_dict(result) -> dict[str, Any]:
    return {
        "hit": result.hit,
        "failures": list(result.failures),
        "references": list(result.references),
        "evidence": _evidence_metrics_to_dict(result.evidence_metrics),
    }


def _evidence_summary_to_dict(summary) -> dict[str, Any]:
    return {
        "total": summary.total,
        "positive_cases": summary.positive_cases,
        "negative_cases": summary.negative_cases,
        "evidence_hit_at_1_rate": summary.evidence_hit_at_1_rate,
        "evidence_hit_at_3_rate": summary.evidence_hit_at_3_rate,
        "evidence_hit_at_5_rate": summary.evidence_hit_at_5_rate,
        "evidence_recall_at_5_avg": summary.evidence_recall_at_5_avg,
        "evidence_mrr_at_5_avg": summary.evidence_mrr_at_5_avg,
        "false_positive_rate": summary.false_positive_rate,
    }


def _evidence_metrics_to_dict(metrics) -> dict[str, Any]:
    return {
        "evidence_hit_at_1": metrics.evidence_hit_at_1,
        "evidence_hit_at_3": metrics.evidence_hit_at_3,
        "evidence_hit_at_5": metrics.evidence_hit_at_5,
        "evidence_recall_at_5": metrics.evidence_recall_at_5,
        "evidence_mrr_at_5": metrics.evidence_mrr_at_5,
        "false_positive": metrics.false_positive,
        "relevant_ranks": list(metrics.relevant_ranks),
        "matched_signal_count": metrics.matched_signal_count,
        "expected_signal_count": metrics.expected_signal_count,
    }


def _ragas_score_to_dict(score: RagasTextScores | None) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "faithfulness": score.faithfulness,
        "answer_relevancy": score.answer_relevancy,
        "errors": dict(score.errors),
    }


def _usage_estimate_to_dict(
    usage: EvaluationUsageEstimate | None,
) -> dict[str, Any] | None:
    if usage is None:
        return None

    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost": usage.estimated_cost,
        "currency": usage.currency,
        "source": usage.source,
    }


def _ragas_summary_to_dict(
    ragas_scores: dict[str, RagasTextScores],
) -> dict[str, Any]:
    scores = list(ragas_scores.values())
    return {
        "total": len(scores),
        "scored": sum(
            1
            for score in scores
            if score.faithfulness is not None or score.answer_relevancy is not None
        ),
        "faithfulness_avg": _average_score(
            score.faithfulness for score in scores
        ),
        "answer_relevancy_avg": _average_score(
            score.answer_relevancy for score in scores
        ),
        "error_count": sum(1 for score in scores if score.errors),
    }


def _average_score(values) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None

    return sum(numbers) / len(numbers)
