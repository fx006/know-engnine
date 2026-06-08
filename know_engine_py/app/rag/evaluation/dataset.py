from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from know_engine_py.app.rag.evaluation.models import (
    EvalFlow,
    EvalCase,
    EvalExpectation,
    EvidenceSignal,
)


SUPPORTED_SCHEMA_VERSION = 2
SUPPORTED_EXPECTATION_KEYS = {
    "expected_flow",
    "evidence_signals",
    "relevant_doc_ids",
    "relevant_chunk_ids",
}
SUPPORTED_EXPECTED_FLOWS = {
    "retrieval",
    "clarification",
    "common_chat",
}
SUPPORTED_SIGNAL_KINDS = {
    "route",
    "document_title",
    "keyword",
    "content",
    "table",
}


def load_retrieval_eval_cases(path: str | Path) -> list[EvalCase]:
    """从 JSONL 文件加载检索评测样例。

    loader 只支持 schema v2，不做旧 schema 运行时兼容。旧数据应通过一次性
    数据集迁移完成，避免把历史字段永久留在主路径里。
    """

    dataset_path = Path(path)
    cases: list[EvalCase] = []
    seen_ids: set[str] = set()

    with dataset_path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"评测集第 {line_no} 行不是合法 JSON") from exc

            case = _case_from_payload(payload, line_no=line_no)
            if case.case_id in seen_ids:
                raise ValueError(f"评测集 case_id 重复：{case.case_id}")

            seen_ids.add(case.case_id)
            cases.append(case)

    return cases


def _case_from_payload(payload: dict[str, Any], *, line_no: int) -> EvalCase:
    schema_version = payload.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"评测集第 {line_no} 行 schema_version 必须是 {SUPPORTED_SCHEMA_VERSION}"
        )

    case_id = _required_string(payload, "case_id", line_no=line_no)
    query = _required_string(payload, "query", line_no=line_no)
    expectation_payload = payload.get("expectation") or {}
    if not isinstance(expectation_payload, dict):
        raise ValueError(f"评测集第 {line_no} 行 expectation 必须是对象")

    unsupported_keys = set(expectation_payload) - SUPPORTED_EXPECTATION_KEYS
    if unsupported_keys:
        supported = ", ".join(sorted(SUPPORTED_EXPECTATION_KEYS))
        found = ", ".join(sorted(unsupported_keys))
        raise ValueError(
            f"评测集第 {line_no} 行 expectation 只支持 {supported}，不支持：{found}"
        )

    return EvalCase(
        case_id=case_id,
        query=query,
        expectation=EvalExpectation(
            expected_flow=_to_expected_flow(
                expectation_payload.get("expected_flow"),
                line_no=line_no,
            ),
            evidence_signals=_to_evidence_signals(
                expectation_payload.get("evidence_signals"),
                line_no=line_no,
            ),
            relevant_doc_ids=_to_tuple(expectation_payload.get("relevant_doc_ids")),
            relevant_chunk_ids=_to_tuple(
                expectation_payload.get("relevant_chunk_ids")
            ),
        ),
        reference_answer=_optional_string(payload.get("reference_answer")),
        negative_expected=bool(payload.get("negative_expected", False)),
        tags=_to_tuple(payload.get("tags")),
        note=_optional_string(payload.get("note")) or "",
    )


def _to_expected_flow(value: Any, *, line_no: int) -> EvalFlow:
    if value in (None, ""):
        return "retrieval"

    expected_flow = str(value).strip()
    if expected_flow not in SUPPORTED_EXPECTED_FLOWS:
        supported = ", ".join(sorted(SUPPORTED_EXPECTED_FLOWS))
        raise ValueError(
            f"评测集第 {line_no} 行不支持的 expected_flow：{expected_flow}，"
            f"当前支持：{supported}"
        )
    return expected_flow  # type: ignore[return-value]


def _to_evidence_signals(
    value: Any,
    *,
    line_no: int,
) -> tuple[EvidenceSignal, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError(f"评测集第 {line_no} 行 evidence_signals 必须是数组")

    signals: list[EvidenceSignal] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"评测集第 {line_no} 行第 {index} 个 evidence signal 必须是对象"
            )

        kind = _required_string(item, "kind", line_no=line_no)
        signal_value = _required_string(item, "value", line_no=line_no)
        if kind not in SUPPORTED_SIGNAL_KINDS:
            supported = ", ".join(sorted(SUPPORTED_SIGNAL_KINDS))
            raise ValueError(
                f"评测集第 {line_no} 行不支持的 evidence signal kind：{kind}，"
                f"当前支持：{supported}"
            )

        signals.append(EvidenceSignal(kind=kind, value=signal_value))

    return tuple(signals)


def _required_string(payload: dict[str, Any], key: str, *, line_no: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"评测集第 {line_no} 行缺少 {key}")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _to_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple | set):
        return tuple(str(item) for item in value if item not in (None, ""))
    return (str(value),)
