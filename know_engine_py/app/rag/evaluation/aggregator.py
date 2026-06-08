from __future__ import annotations

from collections.abc import Iterable, Sequence

from know_engine_py.app.rag.evaluation.models import (
    EvalResult,
    EvalSummary,
    EvidenceMetricsSummary,
)


def summarize_results(results: Sequence[EvalResult]) -> EvalSummary:
    """汇总一批 evidence 评测结果。"""

    result_list = list(results)
    total = len(result_list)
    hits = sum(1 for result in result_list if result.hit)
    misses = total - hits
    return EvalSummary(
        total=total,
        hits=hits,
        misses=misses,
        hit_rate=hits / total if total else 0.0,
        results=result_list,
        evidence_summary=_summarize_evidence_metrics(result_list),
    )


def _summarize_evidence_metrics(
    results: list[EvalResult],
) -> EvidenceMetricsSummary:
    positive_results = [result for result in results if not result.negative_expected]
    negative_results = [result for result in results if result.negative_expected]
    positive_count = len(positive_results)
    negative_count = len(negative_results)

    return EvidenceMetricsSummary(
        total=len(results),
        positive_cases=positive_count,
        negative_cases=negative_count,
        evidence_hit_at_1_rate=_rate(
            sum(
                1
                for result in positive_results
                if result.evidence_metrics.evidence_hit_at_1
            ),
            positive_count,
        ),
        evidence_hit_at_3_rate=_rate(
            sum(
                1
                for result in positive_results
                if result.evidence_metrics.evidence_hit_at_3
            ),
            positive_count,
        ),
        evidence_hit_at_5_rate=_rate(
            sum(
                1
                for result in positive_results
                if result.evidence_metrics.evidence_hit_at_5
            ),
            positive_count,
        ),
        evidence_recall_at_5_avg=_average(
            result.evidence_metrics.evidence_recall_at_5
            for result in positive_results
        ),
        evidence_mrr_at_5_avg=_average(
            result.evidence_metrics.evidence_mrr_at_5 for result in positive_results
        ),
        false_positive_rate=_rate(
            sum(
                1
                for result in negative_results
                if result.evidence_metrics.false_positive
            ),
            negative_count,
        ),
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _average(values: Iterable[float]) -> float:
    value_list = list(values)
    return sum(value_list) / len(value_list) if value_list else 0.0
