from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from know_engine_py.app.rag.evaluation.models import EvalCase


async def run_cli(args: argparse.Namespace) -> Path:
    """从命令行运行检索评测。"""

    from know_engine_py.app.core.settings import get_settings
    from know_engine_py.app.db.session import get_session_maker
    from know_engine_py.app.rag.chat_graph_builder import build_chat_rag_graph_from_db
    from know_engine_py.app.rag.evaluation.dataset import load_retrieval_eval_cases
    from know_engine_py.app.rag.evaluation.ragas_adapter import (
        create_default_ragas_text_adapter,
    )
    from know_engine_py.app.rag.evaluation.report import (
        evaluation_summary_to_dict,
        write_evaluation_report,
    )
    from know_engine_py.app.rag.evaluation.runner import RagEvaluationRunner

    settings = get_settings()
    cases = select_eval_cases(
        load_retrieval_eval_cases(args.dataset),
        case_ids=tuple(args.case_id or ()),
        tags=tuple(args.tag or ()),
    )

    session_maker = get_session_maker()
    async with session_maker() as db:
        graph = build_chat_rag_graph_from_db(db=db, settings=settings)
        runner = RagEvaluationRunner(graph=graph)
        print(f"待评测样例数：{len(cases)}")
        summary = await runner.run_cases(
            cases,
            user_id=args.user_id,
            group_id=args.group_id,
            knowledge_base_id=args.knowledge_base_id,
            on_case_start=_print_case_start,
            on_case_finished=_print_case_finished,
        )

    ragas_scores: dict[str, Any] = {}
    with_ragas = args.with_ragas and not args.dry_run
    if with_ragas:
        adapter = create_default_ragas_text_adapter(settings)
        ragas_scores = await _score_with_ragas(
            adapter=adapter,
            results=summary.results,
            max_concurrency=settings.eval_max_concurrency,
        )

    payload = evaluation_summary_to_dict(summary, ragas_scores=ragas_scores)
    report_path = _resolve_report_path(settings, args.output_dir)
    write_evaluation_report(report_path, payload)
    _print_summary(report_path, payload, with_ragas=with_ragas)
    return report_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="运行 Know-Engine 内部 RAG 评测。",
    )
    parser.add_argument(
        "--dataset",
        default="eval/datasets/automotive_seed.jsonl",
        help="JSONL 评测数据集路径。",
    )
    parser.add_argument(
        "--user-id",
        default="eval-user",
        help="评测使用的用户 ID。",
    )
    parser.add_argument(
        "--group-id",
        default=None,
        help="可选的群组 ID，用作检索范围。",
    )
    parser.add_argument(
        "--knowledge-base-id",
        default=None,
        help="可选的知识库 ID，用作检索范围。",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="只运行指定 case_id；可重复传入。",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="只运行带指定 tag 的样例；可重复传入，多个 tag 按 OR 匹配。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只运行项目业务指标，跳过 RAGAS 评分。",
    )
    parser.add_argument(
        "--with-ragas",
        action="store_true",
        help="运行 RAGAS 纯文本指标；dry-run 模式不要传该参数。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="生成评测报告的目录。",
    )
    return parser


def select_eval_cases(
    cases: list[EvalCase],
    *,
    case_ids: tuple[str, ...],
    tags: tuple[str, ...],
) -> list[EvalCase]:
    """按 CLI 参数筛选评测样例。

    `case_id` 和 `tag` 同时传入时取交集；多个 tag 内部按 OR 匹配。
    """
    normalized_case_ids = {case_id.strip() for case_id in case_ids if case_id.strip()}
    normalized_tags = {tag.strip() for tag in tags if tag.strip()}

    selected = [
        case
        for case in cases
        if _matches_case_filter(case, normalized_case_ids)
        and _matches_tag_filter(case, normalized_tags)
    ]

    if not selected:
        raise ValueError("没有匹配的评测样例，请检查 --case-id 或 --tag")

    return selected


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    asyncio.run(run_cli(args))


def _resolve_report_path(settings: Any, output_dir: str | None) -> Path:
    directory = Path(output_dir or settings.eval_output_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"rag_eval_{timestamp}.json"


async def _score_with_ragas(
    *,
    adapter,
    results,
    max_concurrency: int,
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def score_one(result):
        async with semaphore:
            return result.case.case_id, await adapter.score_case(result)

    scored_pairs = await asyncio.gather(*(score_one(result) for result in results))
    return dict(scored_pairs)


def _matches_case_filter(case: EvalCase, case_ids: set[str]) -> bool:
    if not case_ids:
        return True
    return case.case_id in case_ids


def _matches_tag_filter(case: EvalCase, tags: set[str]) -> bool:
    if not tags:
        return True
    return bool(set(case.tags) & tags)


def _print_case_start(index: int, total: int, case: EvalCase) -> None:
    print(f"[EVAL] {index}/{total} start {case.case_id}: {case.query}")


def _print_case_finished(index: int, total: int, result) -> None:
    status = "hit" if result.flow_result.hit and result.selected_result.hit else "miss"
    print(f"[EVAL] {index}/{total} done  {result.case.case_id}: {status}")


def _print_summary(
    report_path: Path,
    payload: dict,
    *,
    with_ragas: bool,
) -> None:
    flow_summary = payload["flow"]
    selected_summary = payload["retrieval"]["selected"]
    print("RAG 评测完成")
    print(f"- 样例数：{flow_summary['total']}")
    print(f"- flow 命中：{flow_summary['hits']}/{flow_summary['total']}")
    print(f"- flow 命中率：{flow_summary['hit_rate']:.4f}")
    print(
        f"- retrieval selected 证据命中："
        f"{selected_summary['hits']}/{selected_summary['total']}"
    )
    print(f"- retrieval selected 证据命中率：{selected_summary['hit_rate']:.4f}")
    print(f"- RAGAS：{'启用' if with_ragas else '禁用'}")
    if with_ragas:
        ragas_summary = payload.get("generation", {}).get("ragas", {})
        _print_optional_score(
            "RAGAS Faithfulness 平均分",
            ragas_summary.get("faithfulness_avg"),
        )
        _print_optional_score(
            "RAGAS Answer Relevancy 平均分",
            ragas_summary.get("answer_relevancy_avg"),
        )
        _print_usage_estimate(payload.get("generation", {}).get("usage_estimate"))
    print(f"- 报告：{report_path}")


def _print_optional_score(label: str, value: Any) -> None:
    if value is None:
        print(f"- {label}：N/A")
        return

    print(f"- {label}：{float(value):.4f}")


def _print_usage_estimate(usage: dict[str, Any] | None) -> None:
    if not usage:
        print("- RAGAS 可见文本估算 token：N/A")
        print("- RAGAS 估算费用：N/A")
        return

    print(f"- RAGAS 可见文本估算 token：{usage.get('total_tokens', 0)}")
    estimated_cost = usage.get("estimated_cost")
    if estimated_cost is None:
        print("- RAGAS 估算费用：N/A")
        return

    currency = usage.get("currency") or ""
    print(f"- RAGAS 估算费用：{float(estimated_cost):.6f} {currency}".rstrip())


if __name__ == "__main__":
    main()
