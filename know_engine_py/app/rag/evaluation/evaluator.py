from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from know_engine_py.app.rag.evaluation.models import (
    EvalCase,
    EvalResult,
    EvidenceMetrics,
    EvidenceSignal,
)
from know_engine_py.app.rag.utils.reference import build_rag_references


def evaluate_case(
    case: EvalCase,
    documents: list[Document] | tuple[Document, ...],
) -> EvalResult:
    """评估一个样例在某个文档列表上的 evidence 命中情况。"""

    document_list = list(documents)
    references = _normalize_references(document_list)
    evidence_metrics = _calculate_evidence_metrics(case, document_list)

    if case.negative_expected:
        failures = ["负样例不应返回检索证据"] if document_list else []
        return EvalResult(
            case_id=case.case_id,
            query=case.query,
            hit=not failures,
            negative_expected=True,
            failures=failures,
            references=references,
            evidence_metrics=evidence_metrics,
        )

    failures = [
        f"缺少期望证据信号：{signal.kind}={signal.value}"
        for signal in case.expectation.evidence_signals
        if not any(_matches_signal(document, signal) for document in document_list)
    ]
    return EvalResult(
        case_id=case.case_id,
        query=case.query,
        hit=not failures,
        negative_expected=False,
        failures=failures,
        references=references,
        evidence_metrics=evidence_metrics,
    )


def _calculate_evidence_metrics(
    case: EvalCase,
    documents: list[Document],
) -> EvidenceMetrics:
    if case.negative_expected:
        return EvidenceMetrics(false_positive=bool(documents))

    signals = tuple(case.expectation.evidence_signals)
    if not signals:
        return EvidenceMetrics()

    relevant_ranks: list[int] = []
    matched_top_5: set[EvidenceSignal] = set()

    for index, document in enumerate(documents, start=1):
        matched = {
            signal for signal in signals if _matches_signal(document, signal)
        }
        if matched:
            relevant_ranks.append(index)
            if index <= 5:
                matched_top_5.update(matched)

    first_relevant_rank = next(
        (rank for rank in relevant_ranks if rank <= 5),
        None,
    )
    signal_count = len(signals)
    return EvidenceMetrics(
        evidence_hit_at_1=any(rank <= 1 for rank in relevant_ranks),
        evidence_hit_at_3=any(rank <= 3 for rank in relevant_ranks),
        evidence_hit_at_5=any(rank <= 5 for rank in relevant_ranks),
        evidence_recall_at_5=(
            len(matched_top_5) / signal_count if signal_count else 0.0
        ),
        evidence_mrr_at_5=(1 / first_relevant_rank) if first_relevant_rank else 0.0,
        relevant_ranks=relevant_ranks,
        matched_signal_count=len(matched_top_5),
        expected_signal_count=signal_count,
    )


def _matches_signal(document: Document, signal: EvidenceSignal) -> bool:
    metadata = dict(document.metadata or {})
    if signal.kind in ("keyword", "content"):
        return signal.value in (document.page_content or "")
    if signal.kind == "document_title":
        return signal.value in _document_title(metadata)
    if signal.kind == "table":
        return signal.value in set(_to_string_list(metadata.get("tables")))
    if signal.kind == "route":
        return signal.value in _extract_metadata_routes(metadata)
    return False


def _document_title(metadata: dict[str, Any]) -> str:
    return str(
        _first_non_empty(
            metadata.get("documentTitle"),
            metadata.get("document_title"),
            metadata.get("fileName"),
            metadata.get("title"),
        )
        or ""
    )


def _normalize_references(documents: list[Document]) -> list[dict[str, Any]]:
    # 评测需要保留 Text-to-SQL 引用，这类引用通常没有 chunkId。
    return [
        _with_route_fields(dict(reference))
        for reference in build_rag_references(documents, require_chunk_id=False)
    ]


def _with_route_fields(reference: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(reference.get("metadata") or {})
    route = _first_non_empty(
        metadata.get("retrievalRoute"),
        metadata.get("retrievalSource"),
        reference.get("retrievalSource"),
        reference.get("sourceType"),
    )
    if route:
        reference["retrievalRoute"] = str(route)
    return reference


def _extract_metadata_routes(metadata: dict[str, Any]) -> set[str]:
    routes: set[str] = set()
    for key in ("retrievalRoute", "retrievalSource", "sourceType"):
        value = metadata.get(key)
        if value:
            routes.add(str(value))

    sources = metadata.get("retrievalSources")
    if isinstance(sources, list | tuple | set):
        routes.update(str(source) for source in sources if source)

    return routes


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    return [str(value)]
