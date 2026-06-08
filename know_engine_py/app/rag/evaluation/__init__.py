"""RAG 评测模块。

核心检索评测由 models/evaluator/aggregator 三个文件组成；retrieval_eval.py
仅保留兼容导出，避免继续承载新逻辑。
"""

from know_engine_py.app.rag.evaluation.aggregator import summarize_results
from know_engine_py.app.rag.evaluation.evaluator import evaluate_case
from know_engine_py.app.rag.evaluation.models import (
    EvalCase,
    EvalExpectation,
    EvalResult,
    EvalSummary,
    EvidenceMetrics,
    EvidenceMetricsSummary,
    EvidenceSignal,
)

__all__ = [
    "EvalCase",
    "EvalExpectation",
    "EvalResult",
    "EvalSummary",
    "EvidenceMetrics",
    "EvidenceMetricsSummary",
    "EvidenceSignal",
    "evaluate_case",
    "summarize_results",
]
