from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from know_engine_py.app.core.settings import Settings, get_settings


class EmbeddingFactory:
    """创建项目统一使用的 LangChain Embeddings 实例。

    当前通过 DashScope OpenAI-compatible endpoint 创建 OpenAIEmbeddings。
    这里不直接执行向量化，只负责模型对象创建，避免和 VectorStore.aadd_documents()
    的“向量化 + 入库”职责重复。
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def create(self) -> Embeddings:
        """创建 LangChain Embeddings，供 Milvus/ES VectorStore 或 Retriever 使用。"""
        self._validate_settings()

        return OpenAIEmbeddings(
            model=self.settings.embedding_model,
            dimensions=self.settings.embedding_dimensions,
            api_key=self.settings.dashscope_api_key,
            base_url=self.settings.dashscope_base_url.rstrip("/"),
            check_embedding_ctx_length=False,
        )

    def _validate_settings(self) -> None:
        if not self.settings.dashscope_api_key.strip():
            raise ValueError("DASHSCOPE_API_KEY 不能为空")