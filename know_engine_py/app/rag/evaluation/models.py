from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EvalFlow = Literal["retrieval", "clarification", "common_chat"]


@dataclass(frozen=True)
class EvidenceSignal:
    """一个通用证据信号。

    kind 说明匹配维度，value 是期望值。匹配策略由 evaluator 统一定义，
    数据集不携带 operator/weight/source 这类小 DSL。
    """

    kind: str
    value: str


@dataclass(frozen=True)
class EvalExpectation:
    """单条样例的期望证据。

    relevant_* 字段是标准 IR 评测预留，本轮只实现 evidence_signals。
    """

    expected_flow: EvalFlow = "retrieval"
    evidence_signals: tuple[EvidenceSignal, ...] = ()
    relevant_doc_ids: tuple[str, ...] = ()
    relevant_chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalCase:
    """稳定的 RAG 评测样例。"""

    case_id: str
    query: str
    expectation: EvalExpectation
    reference_answer: str | None = None
    negative_expected: bool = False
    tags: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class EvidenceMetrics:
    """基于 evidence_signals 的工程化检索指标。

    这些字段不是标准 IR 指标；它们衡量的是 Top-K 是否覆盖了已标注的
    业务证据信号。
    """

    evidence_hit_at_1: bool = False
    evidence_hit_at_3: bool = False
    evidence_hit_at_5: bool = False
    evidence_recall_at_5: float = 0.0
    evidence_mrr_at_5: float = 0.0
    false_positive: bool = False
    relevant_ranks: list[int] = field(default_factory=list)
    matched_signal_count: int = 0
    expected_signal_count: int = 0


@dataclass(frozen=True)
class EvidenceMetricsSummary:
    """一批样例的 evidence 指标汇总。"""

    total: int
    positive_cases: int
    negative_cases: int
    evidence_hit_at_1_rate: float
    evidence_hit_at_3_rate: float
    evidence_hit_at_5_rate: float
    evidence_recall_at_5_avg: float
    evidence_mrr_at_5_avg: float
    false_positive_rate: float


@dataclass(frozen=True)
class EvalResult:
    """单条样例在某个检索结果列表上的评测结果。"""

    case_id: str
    query: str
    hit: bool
    negative_expected: bool = False
    failures: list[str] = field(default_factory=list)
    references: list[dict[str, Any]] = field(default_factory=list)
    evidence_metrics: EvidenceMetrics = field(default_factory=EvidenceMetrics)


@dataclass(frozen=True)
class FlowEvalResult:
    """单条样例的 LangGraph 链路走向评测结果。"""

    case_id: str
    query: str
    expected_flow: str
    actual_flow: str
    hit: bool
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlowEvalSummary:
    """一批样例的链路走向汇总。"""

    total: int
    hits: int
    misses: int
    hit_rate: float
    results: list[FlowEvalResult]


@dataclass(frozen=True)
class EvalSummary:
    """一批样例的评测汇总。"""

    total: int
    hits: int
    misses: int
    hit_rate: float
    results: list[EvalResult]
    evidence_summary: EvidenceMetricsSummary
