from __future__ import annotations

from know_engine_py.app.rag.evaluation.aggregator import summarize_results
from know_engine_py.app.rag.evaluation.evaluator import evaluate_case
from know_engine_py.app.rag.evaluation.flow import evaluate_flow, summarize_flow_results
from know_engine_py.app.rag.evaluation.models import (
    EvalFlow,
    EvalCase,
    EvalExpectation,
    EvalResult,
    EvalSummary,
    EvidenceMetrics,
    EvidenceMetricsSummary,
    EvidenceSignal,
    FlowEvalResult,
    FlowEvalSummary,
)

# Backward-compatible aliases for older imports. New code should import from
# models.py, evaluator.py and aggregator.py directly.
RetrievalEvalCase = EvalCase
RetrievalEvalExpectation = EvalExpectation
RetrievalEvalResult = EvalResult
RetrievalEvalSummary = EvalSummary
RetrievalRankingMetrics = EvidenceMetrics
RetrievalRankingSummary = EvidenceMetricsSummary

evaluate_retrieval_case = evaluate_case
summarize_retrieval_eval = summarize_results

__all__ = [
    "EvalFlow",
    "EvalCase",
    "EvalExpectation",
    "EvalResult",
    "EvalSummary",
    "EvidenceMetrics",
    "EvidenceMetricsSummary",
    "EvidenceSignal",
    "FlowEvalResult",
    "FlowEvalSummary",
    "RetrievalEvalCase",
    "RetrievalEvalExpectation",
    "RetrievalEvalResult",
    "RetrievalEvalSummary",
    "RetrievalRankingMetrics",
    "RetrievalRankingSummary",
    "evaluate_case",
    "evaluate_flow",
    "evaluate_retrieval_case",
    "summarize_flow_results",
    "summarize_results",
    "summarize_retrieval_eval",
]
