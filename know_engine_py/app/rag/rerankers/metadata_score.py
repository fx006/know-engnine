from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document

from know_engine_py.app.rag.rerankers.base import copy_document_with_metadata


class MetadataScoreReranker:
    """根据已有检索分数做确定性排序的轻量 reranker。

    这不是语义重排序模型，只是 Day7 阶段用于跑通 reranker 契约的安全兜底。
    真实 BGE/CrossEncoder reranker 后续实现同一个 arerank() 协议即可替换。
    """

    score_keys = ("rerankScore", "rerankedScore", "rrfScore", "score", "_score")

    async def arerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> list[Document]:
        scored_documents = [
            (
                self._read_score(document.metadata or {}),
                index,
                document,
            )
            for index, document in enumerate(documents)
        ]
        scored_documents.sort(key=lambda item: (item[0], -item[1]), reverse=True)

        limit = top_k if top_k is not None else len(scored_documents)
        selected = scored_documents[:limit]

        return [
            copy_document_with_metadata(
                document,
                {"rerankScore": score},
            )
            for score, _, document in selected
        ]

    def _read_score(self, metadata: dict[str, Any]) -> float:
        for key in self.score_keys:
            value = metadata.get(key)
            if value in (None, ""):
                continue

            try:
                return float(value)
            except (TypeError, ValueError):
                continue

        return 0.0
