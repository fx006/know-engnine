from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.rag.evaluation.runner import EvaluationCaseRunResult
from know_engine_py.app.rag.evaluation.usage import (
    EvaluationUsageEstimate,
    estimate_ragas_visible_text_usage,
)


class RagasScorer(Protocol):
    """RAGAS 指标使用的最小异步评分器契约。"""

    async def ascore(self, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class RagasTextScores:
    """单条样例的 RAGAS 纯文本评分结果。"""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    errors: dict[str, str] = field(default_factory=dict)
    usage_estimate: EvaluationUsageEstimate = field(
        default_factory=EvaluationUsageEstimate
    )


class RagasTextEvaluationAdapter:
    """使用 RAGAS 纯文本指标评估生成质量。

    该适配器只向 RAGAS 传递普通字符串和 list[str] 上下文，不使用 URL、
    文件或多模态输入。
    """

    def __init__(
        self,
        *,
        faithfulness_scorer: RagasScorer,
        answer_relevancy_scorer: RagasScorer,
        model_name: str | None = None,
        input_cost_per_1k_tokens: float | None = None,
        output_cost_per_1k_tokens: float | None = None,
        cost_currency: str = "CNY",
    ):
        self.faithfulness_scorer = faithfulness_scorer
        self.answer_relevancy_scorer = answer_relevancy_scorer
        self.model_name = model_name
        self.input_cost_per_1k_tokens = input_cost_per_1k_tokens
        self.output_cost_per_1k_tokens = output_cost_per_1k_tokens
        self.cost_currency = cost_currency

    async def score_case(
        self,
        result: EvaluationCaseRunResult,
    ) -> RagasTextScores:
        response = (result.response or "").strip()
        if not response:
            return RagasTextScores(
                errors={"response": "回答为空，跳过 RAGAS 文本评测"}
            )

        errors: dict[str, str] = {}
        faithfulness = await self._score_faithfulness(
            result,
            response=response,
            errors=errors,
        )
        answer_relevancy = await self._score_answer_relevancy(
            result,
            response=response,
            errors=errors,
        )
        usage_estimate = estimate_ragas_visible_text_usage(
            query=result.case.query,
            response=response,
            contexts=result.retrieved_contexts,
            model=self.model_name,
            input_cost_per_1k_tokens=self.input_cost_per_1k_tokens,
            output_cost_per_1k_tokens=self.output_cost_per_1k_tokens,
            currency=self.cost_currency,
        )
        return RagasTextScores(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            errors=errors,
            usage_estimate=usage_estimate,
        )

    async def _score_faithfulness(
        self,
        result: EvaluationCaseRunResult,
        *,
        response: str,
        errors: dict[str, str],
    ) -> float | None:
        if not result.retrieved_contexts:
            errors["faithfulness"] = "检索上下文为空，跳过 Faithfulness"
            return None

        try:
            score = await self.faithfulness_scorer.ascore(
                user_input=result.case.query,
                response=response,
                retrieved_contexts=result.retrieved_contexts,
            )
            return _score_value(score)
        except Exception as exc:
            errors["faithfulness"] = str(exc)
            return None

    async def _score_answer_relevancy(
        self,
        result: EvaluationCaseRunResult,
        *,
        response: str,
        errors: dict[str, str],
    ) -> float | None:
        try:
            score = await self.answer_relevancy_scorer.ascore(
                user_input=result.case.query,
                response=response,
            )
            return _score_value(score)
        except Exception as exc:
            errors["answer_relevancy"] = str(exc)
            return None


def create_default_ragas_text_adapter(
    settings: Settings | None = None,
) -> RagasTextEvaluationAdapter:
    """根据项目配置创建默认 RAGAS 适配器。"""

    resolved_settings = settings or get_settings()
    _validate_settings(resolved_settings)

    if resolved_settings.ragas_do_not_track:
        os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness

    client = AsyncOpenAI(
        api_key=resolved_settings.dashscope_api_key,
        base_url=resolved_settings.dashscope_base_url.rstrip("/"),
    )
    llm = llm_factory(
        resolved_settings.eval_llm_model or resolved_settings.llm_chat_model,
        client=client,
        temperature=0,
        seed=42,
        max_tokens=resolved_settings.eval_llm_max_tokens,
        extra_body={"enable_thinking": False},
    )
    embeddings = embedding_factory(
        "openai",
        model=resolved_settings.eval_embedding_model
        or resolved_settings.embedding_model,
        client=client,
    )
    return RagasTextEvaluationAdapter(
        faithfulness_scorer=Faithfulness(llm=llm),
        answer_relevancy_scorer=AnswerRelevancy(
            llm=llm,
            embeddings=embeddings,
        ),
        model_name=resolved_settings.eval_llm_model
        or resolved_settings.llm_chat_model,
        input_cost_per_1k_tokens=resolved_settings.eval_input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=resolved_settings.eval_output_cost_per_1k_tokens,
        cost_currency=resolved_settings.eval_cost_currency,
    )


def _validate_settings(settings: Settings) -> None:
    if not settings.dashscope_api_key.strip():
        raise ValueError("DASHSCOPE_API_KEY 不能为空")


def _score_value(score: Any) -> float:
    value = getattr(score, "value", score)
    return float(value)
