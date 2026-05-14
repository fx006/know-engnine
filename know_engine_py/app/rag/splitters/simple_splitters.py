from __future__ import annotations

from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter


class LengthTextSplitter:
    """LENGTH 策略：用 LangChain RecursiveCharacterTextSplitter 做基础长度切分。"""

    def __init__(
        self,
        chunk_size: int = 800,
        overlap: int = 80,
        separators: list[str] | None = None,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须大于等于 0，并且小于 chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=separators or [
                "\n\n",
                "\n",
                "。",
                "！",
                "？",
                "；",
                "，",
                "、",
                " ",
                "",
            ],
        )

    def split(self, text: str, base_metadata: dict | None = None) -> list[Document]:
        """切分普通文本，并补充项目统一 metadata。"""
        return _with_project_metadata(
            self._splitter.create_documents(
                [text.strip()],
                metadatas=[base_metadata or {}],
            )
        )


class SeparatorTextSplitter:
    """SEPARATOR 策略：用 LangChain CharacterTextSplitter 按固定分隔符切分。"""

    def __init__(self, separator: str, chunk_size: int = 800, overlap: int = 0):
        if not separator:
            raise ValueError("separator 不能为空")
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须大于等于 0，并且小于 chunk_size")

        self.separator = separator
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._splitter = CharacterTextSplitter(
            separator=separator,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )

    def split(self, text: str, base_metadata: dict | None = None) -> list[Document]:
        """按固定分隔符切分，并补充项目统一 metadata。"""
        return _with_project_metadata(
            self._splitter.create_documents(
                [text.strip()],
                metadatas=[base_metadata or {}],
            )
        )


class RegexTextSplitter:
    """REGEX 策略：用 LangChain CharacterTextSplitter 按正则分隔符切分。"""

    def __init__(self, regex: str, chunk_size: int = 800, overlap: int = 0):
        if not regex:
            raise ValueError("regex 不能为空")
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须大于等于 0，并且小于 chunk_size")

        self.regex = regex
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._splitter = CharacterTextSplitter(
            separator=regex,
            is_separator_regex=True,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )

    def split(self, text: str, base_metadata: dict | None = None) -> list[Document]:
        """按正则分隔符切分，并补充项目统一 metadata。"""
        return _with_project_metadata(
            self._splitter.create_documents(
                [text.strip()],
                metadatas=[base_metadata or {}],
            )
        )


def _with_project_metadata(documents: list[Document]) -> list[Document]:
    """给 LangChain Document 补充 Know-Engine 需要的 chunk metadata。"""
    result: list[Document] = []

    for part_index, document in enumerate(documents):
        if not document.page_content.strip():
            continue

        metadata = {
            **document.metadata,
            "chunkId": uuid4().hex,
            "partIndex": part_index,
        }
        result.append(
            Document(
                page_content=document.page_content,
                metadata=metadata,
            )
        )

    return result
