from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import model_validator


class HybridRetriever(BaseRetriever):
    """使用 RRF 融合多个 LangChain Retriever 的结果。"""

    retrievers: list[BaseRetriever]
    source_names: list[str] | None = None
    top_k: int = 5
    rrf_k: int = 60

    @model_validator(mode="after")
    def validate_config(self) -> "HybridRetriever":
        if not self.retrievers:
            raise ValueError("retrievers 不能为空")

        if self.source_names is not None and len(self.source_names) != len(self.retrievers):
            raise ValueError("source_names 数量必须与 retrievers 一致")

        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        if self.rrf_k <= 0:
            raise ValueError("rrf_k 必须大于 0")

        return self

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        raise NotImplementedError("HybridRetriever 只支持异步检索，请使用 ainvoke()")

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """并发调用多个 retriever，并用 RRF 合并排序。"""
        results = await asyncio.gather(
            *(retriever.ainvoke(query) for retriever in self.retrievers)
        )
        return self._merge_results(results)

    def _merge_results(self, results: list[list[Document]]) -> list[Document]:
        scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, Document] = {}
        sources: dict[str, list[str]] = defaultdict(list)
        ranks: dict[str, dict[str, int]] = defaultdict(dict)

        for retriever_index, documents in enumerate(results):
            source_name = self._source_name(retriever_index)

            for rank, document in enumerate(documents, start=1):
                key = self._document_key(document)
                scores[key] += 1 / (self.rrf_k + rank)

                if key not in doc_map:
                    doc_map[key] = document

                if source_name not in sources[key]:
                    sources[key].append(source_name)

                ranks[key][source_name] = rank

        sorted_keys = sorted(scores, key=scores.get, reverse=True)[: self.top_k]

        return [
            self._with_fusion_metadata(
                document=doc_map[key],
                key=key,
                score=scores[key],
                sources=sources[key],
                ranks=ranks[key],
            )
            for key in sorted_keys
        ]

    def _source_name(self, index: int) -> str:
        if self.source_names is None:
            return f"retriever_{index}"
        return self.source_names[index]

    def _document_key(self, document: Document) -> str:
        metadata = document.metadata or {}
        chunk_id = metadata.get("chunkId")
        if chunk_id:
            return str(chunk_id)

        if document.id:
            return str(document.id)

        return document.page_content

    def _with_fusion_metadata(
        self,
        *,
        document: Document,
        key: str,
        score: float,
        sources: list[str],
        ranks: dict[str, int],
    ) -> Document:
        metadata: dict[str, Any] = dict(document.metadata or {})
        metadata["retrievalKey"] = key
        metadata["rrfScore"] = score
        metadata["retrievalSources"] = sources
        metadata["retrievalRanks"] = ranks

        return Document(
            id=document.id,
            page_content=document.page_content,
            metadata=metadata,
        )