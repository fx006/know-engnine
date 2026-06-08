from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Protocol

from langchain_core.documents import Document

from know_engine_py.app.rag.evaluation.aggregator import summarize_results
from know_engine_py.app.rag.evaluation.context import documents_to_ragas_contexts
from know_engine_py.app.rag.evaluation.evaluator import evaluate_case
from know_engine_py.app.rag.evaluation.flow import (
    evaluate_flow,
    summarize_flow_results,
)
from know_engine_py.app.rag.evaluation.models import (
    EvalCase,
    EvalResult,
    EvalSummary,
    FlowEvalResult,
    FlowEvalSummary,
)
from know_engine_py.app.rag.state import AgentState, build_initial_state


class EvaluationGraph(Protocol):
    """评测 runner 依赖的最小图执行契约。"""

    async def ainvoke(self, input: AgentState) -> AgentState:
        ...


@dataclass(frozen=True)
class EvaluationCaseRunResult:
    """单条样例的完整评测输出。"""

    case: EvalCase
    response: str | None
    flow_result: FlowEvalResult
    retrieved_result: EvalResult
    selected_result: EvalResult
    retrieved_docs: list[Document]
    selected_docs: list[Document]
    rag_references: list[dict[str, Any]]
    retrieved_contexts: list[str]
    route_plan: list[dict]
    route_planner_source: str | None
    error: str | None
    elapsed_ms: float
    final_state: AgentState


@dataclass(frozen=True)
class EvaluationRunSummary:
    """批量评测汇总结果。"""

    flow_summary: FlowEvalSummary
    retrieved_summary: EvalSummary
    selected_summary: EvalSummary
    results: list[EvaluationCaseRunResult]
    elapsed_ms: float


class RagEvaluationRunner:
    """通过 LangGraph 运行评测样例，并避免聊天持久化副作用。

    评测 runner 会刻意绕开 ChatApplicationService.run_chat()。评测过程不应创建会话、
    保存聊天消息，也不应加载短期记忆。
    """

    def __init__(self, *, graph: EvaluationGraph, domain_id: str = "automotive"):
        self.graph = graph
        self.domain_id = domain_id

    async def run_case(
        self,
        case: EvalCase,
        *,
        user_id: str,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
        max_retries: int = 2,
    ) -> EvaluationCaseRunResult:
        start = perf_counter()
        initial_state = build_initial_state(
            query=case.query,
            user_id=user_id,
            domain_id=self.domain_id,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
            chat_history=[],
            max_retries=max_retries,
        )
        final_state = await self.graph.ainvoke(initial_state)
        elapsed_ms = (perf_counter() - start) * 1000

        retrieved_docs = _resolve_documents(final_state, "retrieved_docs")
        selected_docs = _resolve_documents(final_state, "selected_docs")
        rag_references = list(final_state.get("rag_references") or [])
        flow_result = evaluate_flow(case, final_state)
        retrieved_result = evaluate_case(case, retrieved_docs)
        selected_result = evaluate_case(case, selected_docs)
        generation_context_docs = selected_docs or retrieved_docs

        return EvaluationCaseRunResult(
            case=case,
            response=final_state.get("response"),
            flow_result=flow_result,
            retrieved_result=retrieved_result,
            selected_result=selected_result,
            retrieved_docs=retrieved_docs,
            selected_docs=selected_docs,
            rag_references=rag_references,
            retrieved_contexts=documents_to_ragas_contexts(generation_context_docs),
            route_plan=final_state.get("route_plan") or [],
            route_planner_source=final_state.get("route_planner_source"),
            error=final_state.get("error"),
            elapsed_ms=elapsed_ms,
            final_state=final_state,
        )

    async def run_cases(
        self,
        cases: Sequence[EvalCase],
        *,
        user_id: str,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
        on_case_start: Callable[[int, int, EvalCase], None] | None = None,
        on_case_finished: Callable[
            [int, int, EvaluationCaseRunResult], None
        ] | None = None,
    ) -> EvaluationRunSummary:
        start = perf_counter()
        total = len(cases)
        results: list[EvaluationCaseRunResult] = []

        for index, case in enumerate(cases, start=1):
            if on_case_start is not None:
                on_case_start(index, total, case)

            result = await self.run_case(
                case,
                user_id=user_id,
                group_id=group_id,
                knowledge_base_id=knowledge_base_id,
            )
            results.append(result)

            if on_case_finished is not None:
                on_case_finished(index, total, result)

        elapsed_ms = (perf_counter() - start) * 1000
        retrieval_results = [
            result
            for result in results
            if result.case.expectation.expected_flow == "retrieval"
        ]
        return EvaluationRunSummary(
            flow_summary=summarize_flow_results(
                [result.flow_result for result in results]
            ),
            retrieved_summary=summarize_results(
                [result.retrieved_result for result in retrieval_results]
            ),
            selected_summary=summarize_results(
                [result.selected_result for result in retrieval_results]
            ),
            results=results,
            elapsed_ms=elapsed_ms,
        )


def _resolve_documents(state: AgentState, key: str) -> list[Document]:
    return list(state.get(key) or [])
