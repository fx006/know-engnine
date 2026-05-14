from __future__ import annotations

from typing import Protocol

from langchain_core.documents import Document

from know_engine_py.app.rag.splitters.document_splitter import DocumentSplitter
from know_engine_py.app.rag.splitters.simple_splitters import (
    LengthTextSplitter,
    RegexTextSplitter,
    SeparatorTextSplitter,
)
from know_engine_py.app.rag.splitters.types import DocumentSplitParam, SplitType


class TextSplitter(Protocol):
    """所有 splitter 的最小协议：输入文本和基础 metadata，输出 LangChain Document。"""

    def split(
        self,
        text: str,
        base_metadata: dict | None = None,
    ) -> list[Document]:
        ...


class SplitterFactory:
    """根据 DocumentSplitParam 创建具体文档切分器。"""

    @staticmethod
    def create(param: DocumentSplitParam) -> TextSplitter:
        if param.split_type == SplitType.TITLE:
            return DocumentSplitter(
                chunk_size=param.chunk_size,
                overlap=param.overlap,
            )

        if param.split_type == SplitType.LENGTH:
            return LengthTextSplitter(
                chunk_size=param.chunk_size,
                overlap=param.overlap,
            )

        if param.split_type == SplitType.SEPARATOR:
            return SeparatorTextSplitter(
                separator=param.separator or "",
                chunk_size=param.chunk_size,
                overlap=param.overlap,
            )

        if param.split_type == SplitType.REGEX:
            return RegexTextSplitter(
                regex=param.regex or "",
                chunk_size=param.chunk_size,
                overlap=param.overlap,
            )

        if param.split_type == SplitType.SMART:
            smart_overlap = max(1, int(param.chunk_size * 0.1))
            return DocumentSplitter(
                chunk_size=param.chunk_size,
                overlap=smart_overlap,
            )

        raise ValueError(f"不支持的切分策略: {param.split_type}")
