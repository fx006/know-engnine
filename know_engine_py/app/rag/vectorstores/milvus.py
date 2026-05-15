from __future__ import annotations

from typing import Type

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_milvus import Milvus

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.rag.embeddings.factory import EmbeddingFactory


class MilvusVectorStoreFactory:
    """创建项目使用的 LangChain Milvus VectorStore。

    这里不自研向量库协议，只负责把项目配置、embedding 模型
    和 LangChain Milvus 构造参数集中起来。
    """

    def __init__(
        self,
        settings: Settings | None = None,
        embeddings: Embeddings | None = None,
        milvus_cls: Type[Milvus] = Milvus,
    ):
        self.settings = settings or get_settings()
        self.embeddings = embeddings or EmbeddingFactory(settings=self.settings).create()
        self.milvus_cls = milvus_cls

    def create(self) -> VectorStore:
        """创建 Milvus VectorStore，供 DocumentIndexingService 写入和 Retriever 检索使用。"""
        self._validate_milvus_settings()

        return self.milvus_cls(
            embedding_function=self.embeddings,
            collection_name=self.settings.milvus_collection,
            connection_args={"uri": self.settings.milvus_uri},
            text_field="text",
            vector_field="vector",
            metadata_field="metadata",
            auto_id=False,
        )

    def _validate_milvus_settings(self) -> None:
        if not self.settings.milvus_uri.strip():
            raise ValueError("MILVUS_URI 不能为空")
