from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class EvaluationUsageEstimate:
    """评测链路的 token / cost 估算结果。

    当前不是云厂商账单级 usage，而是基于评测可见文本的估算值；真实 provider
    usage 需要后续统一接入 LLM callback 或 RAGAS cost callback。
    """

    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float | None = None
    currency: str = "CNY"
    source: str = "ragas_visible_text_estimate"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_ragas_visible_text_usage(
    *,
    query: str,
    response: str,
    contexts: list[str],
    model: str | None = None,
    input_cost_per_1k_tokens: float | None = None,
    output_cost_per_1k_tokens: float | None = None,
    currency: str = "CNY",
) -> EvaluationUsageEstimate:
    """估算 RAGAS 两个文本指标可见输入的 token 和成本。

    Faithfulness 会使用 query、response、contexts；AnswerRelevancy 会使用
    query、response。RAGAS 内部 prompt 和 judge 输出 token 当前不可见，因此这里
    明确标记为 visible text estimate。
    """
    faithfulness_input = "\n".join([query, response, *contexts])
    answer_relevancy_input = "\n".join([query, response])
    input_tokens = count_text_tokens(faithfulness_input, model=model) + count_text_tokens(
        answer_relevancy_input,
        model=model,
    )
    output_tokens = 0
    estimated_cost = estimate_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )
    return EvaluationUsageEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        currency=currency,
    )


def count_text_tokens(text: str, *, model: str | None = None) -> int:
    """使用 tiktoken 估算文本 token 数；不可用时退化为字符估算。"""
    if not text:
        return 0

    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model or "")
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return max(1, ceil(len(text) / 4))


def estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1k_tokens: float | None,
    output_cost_per_1k_tokens: float | None,
) -> float | None:
    """按每 1K token 单价估算成本；未配置单价时返回 None。"""
    has_input_rate = input_cost_per_1k_tokens is not None and input_cost_per_1k_tokens > 0
    has_output_rate = (
        output_cost_per_1k_tokens is not None and output_cost_per_1k_tokens > 0
    )
    if not has_input_rate and not has_output_rate:
        return None

    input_rate = input_cost_per_1k_tokens if has_input_rate else 0.0
    output_rate = output_cost_per_1k_tokens
    if output_rate is None or output_rate <= 0:
        output_rate = input_rate

    return (input_tokens / 1000 * input_rate) + (output_tokens / 1000 * output_rate)


def sum_usage_estimates(
    estimates: list[EvaluationUsageEstimate],
) -> EvaluationUsageEstimate:
    """汇总多条样例的 usage estimate。"""
    input_tokens = sum(estimate.input_tokens for estimate in estimates)
    output_tokens = sum(estimate.output_tokens for estimate in estimates)
    costs = [estimate.estimated_cost for estimate in estimates]
    estimated_cost = None
    if costs and all(cost is not None for cost in costs):
        estimated_cost = sum(float(cost) for cost in costs if cost is not None)

    currency = estimates[0].currency if estimates else "CNY"
    source = estimates[0].source if estimates else "ragas_visible_text_estimate"
    return EvaluationUsageEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        currency=currency,
        source=source,
    )
