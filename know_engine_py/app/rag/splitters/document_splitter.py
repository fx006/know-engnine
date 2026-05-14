from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(slots=True)
class SectionNode:
    """Markdown 标题树节点，只保存当前标题下的直接正文。"""

    level: int
    heading: str
    heading_path: list[str]
    heading_levels: list[int]
    lines: list[str] = field(default_factory=list)
    children: list["SectionNode"] = field(default_factory=list)


class DocumentSplitter:
    """Markdown/txt 文档切分器。

    当前策略：
    1. 先解析 Markdown 标题树，标题只作为语义边界。
    2. 有直接正文的标题节点才生成 chunk。
    3. chunk 内容直接包含完整父标题链，提高 embedding 和 LLM 上下文质量。
    4. 超长 chunk 生成 parent/child：parent skipEmbedding=1，child 带 parentChunkId。
    5. child chunk 也重复携带完整标题链，避免向量化时丢失父级语义。
    """

    DEFAULT_SEPARATORS = [
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
    ]

    def __init__(
        self,
        chunk_size: int = 800,
        overlap: int = 80,
        separators: list[str] | None = None,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0:
            raise ValueError("overlap 不能小于 0")
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = separators or self.DEFAULT_SEPARATORS

    def split(self, text: str, base_metadata: dict | None = None) -> list[Document]:
        """将 Markdown/txt 文本切分为 LangChain Document 列表。"""
        base_metadata = base_metadata or {}

        root = self._parse_markdown_to_tree(text)
        semantic_documents = self._build_semantic_documents(root, base_metadata)
        return self._apply_parent_child_split(semantic_documents)

    def _parse_markdown_to_tree(self, text: str) -> SectionNode:
        """把 Markdown 文本解析成标题树，并避免把代码块里的 # 识别成标题。"""
        root = SectionNode(
            level=0,
            heading="",
            heading_path=[],
            heading_levels=[],
        )
        stack: list[SectionNode] = [root]

        in_code_block = False
        opening_fence = ""

        for raw_line in text.splitlines():
            line = raw_line.rstrip()

            # 代码块围栏只负责切换状态，围栏行本身仍属于当前节点正文。
            fence = self._parse_code_fence(line)
            if fence is not None:
                stack[-1].lines.append(line)

                if not in_code_block:
                    in_code_block = True
                    opening_fence = fence
                elif fence == opening_fence:
                    in_code_block = False
                    opening_fence = ""

                continue

            # 代码块内的 # 是代码内容，不参与 Markdown 标题识别。
            if in_code_block:
                stack[-1].lines.append(line)
                continue

            # Markdown 标题只建立树结构；是否生成 chunk 由后续“是否有直接正文”决定。
            header = self._parse_header(line)
            if header is not None:
                level, heading = header

                while stack and stack[-1].level >= level:
                    stack.pop()

                parent = stack[-1]
                node = SectionNode(
                    level=level,
                    heading=heading,
                    heading_path=[*parent.heading_path, heading],
                    heading_levels=[*parent.heading_levels, level],
                )
                parent.children.append(node)
                stack.append(node)
                continue

            # 普通正文只挂到当前标题节点，避免父标题吞掉子标题正文。
            stack[-1].lines.append(line)

        return root

    def _build_semantic_documents(
        self,
        root: SectionNode,
        base_metadata: dict,
    ) -> list[Document]:
        """从标题树生成语义 Document：有直接正文的节点才生成。"""
        documents: list[Document] = []

        def walk(node: SectionNode) -> None:
            # 只保留有直接正文的节点，避免生成“只有标题”的低价值 chunk。
            if self._has_effective_content(node.lines):
                metadata = {
                    **base_metadata,
                    "chunkId": self._new_chunk_id(),
                    "headingPath": node.heading_path,
                    "headingLevels": node.heading_levels,
                    "headerLevel": node.level,
                }
                documents.append(
                    Document(
                        page_content=self._build_document_content(node),
                        metadata=metadata,
                    )
                )

            for child in node.children:
                walk(child)

        walk(root)
        return documents

    def _apply_parent_child_split(self, documents: list[Document]) -> list[Document]:
        """对超长语义 Document 做父子分块。"""
        final_documents: list[Document] = []

        for document in documents:
            if len(document.page_content) <= self.chunk_size:
                final_documents.append(document)
                continue

            # 原始语义 chunk 作为 parent，保留完整上下文但不参与 embedding。
            parent_chunk_id = document.metadata["chunkId"]
            parent_metadata = {
                **document.metadata,
                "skipEmbedding": 1,
            }
            final_documents.append(
                Document(
                    page_content=document.page_content,
                    metadata=parent_metadata,
                )
            )

            for part_index, child_text in enumerate(self._split_child_documents(document)):
                child_metadata = {
                    **document.metadata,
                    "chunkId": self._new_chunk_id(),
                    "parentChunkId": parent_chunk_id,
                    "partIndex": part_index,
                }
                final_documents.append(
                    Document(
                        page_content=child_text,
                        metadata=child_metadata,
                    )
                )

        return final_documents

    def _build_document_content(self, node: SectionNode) -> str:
        """构造 chunk 正文：完整父标题链 + 当前节点直接正文。"""
        direct_content = "\n".join(node.lines).strip()

        heading_prefix = self._build_heading_prefix(
            heading_levels=node.heading_levels,
            heading_path=node.heading_path,
        )
        return self._join_heading_and_body(heading_prefix, direct_content)

    def _split_child_documents(self, document: Document) -> list[str]:
        """切分超长 chunk，并确保每个 child 都携带完整父标题链。"""
        heading_prefix = self._build_heading_prefix_from_metadata(document.metadata)
        body_text = self._extract_body_text(document.page_content, heading_prefix)

        # child 的最终内容会再拼一次 heading_prefix，所以 body 的可用长度要扣掉标题部分。
        prefix_cost = len(heading_prefix) + 2 if heading_prefix else 0
        body_chunk_size = max(1, self.chunk_size - prefix_cost)
        body_overlap = min(self.overlap, max(0, body_chunk_size - 1))

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=body_chunk_size,
            chunk_overlap=body_overlap,
            separators=self.separators,
        )
        body_chunks = splitter.split_text(body_text)

        return [
            self._join_heading_and_body(heading_prefix, body_chunk)
            for body_chunk in body_chunks
            if body_chunk.strip()
        ]

    def _build_heading_prefix_from_metadata(self, metadata: dict) -> str:
        heading_path = metadata.get("headingPath") or []
        heading_levels = metadata.get("headingLevels") or list(
            range(1, len(heading_path) + 1)
        )
        return self._build_heading_prefix(
            heading_levels=heading_levels,
            heading_path=heading_path,
        )

    def _build_heading_prefix(
        self,
        *,
        heading_levels: list[int],
        heading_path: list[str],
    ) -> str:
        heading_lines = [
            f"{'#' * level} {heading}"
            for level, heading in zip(heading_levels, heading_path)
        ]
        return "\n".join(heading_lines).strip()

    def _extract_body_text(self, page_content: str, heading_prefix: str) -> str:
        content = page_content.strip()
        if heading_prefix and content.startswith(heading_prefix):
            return content[len(heading_prefix):].strip()
        return content

    def _join_heading_and_body(self, heading_prefix: str, body_text: str) -> str:
        heading_prefix = heading_prefix.strip()
        body_text = body_text.strip()

        if heading_prefix and body_text:
            return f"{heading_prefix}\n\n{body_text}"
        if heading_prefix:
            return heading_prefix
        return body_text

    def _has_effective_content(self, lines: list[str]) -> bool:
        return bool("\n".join(lines).strip())

    def _parse_header(self, line: str) -> tuple[int, str] | None:
        stripped = line.strip()
        if not stripped.startswith("#"):
            return None

        level = len(stripped) - len(stripped.lstrip("#"))
        if level > 6:
            return None
        if len(stripped) == level or stripped[level] != " ":
            return None

        heading = stripped[level:].strip()
        if not heading:
            return None

        return level, heading

    def _parse_code_fence(self, line: str) -> str | None:
        stripped = line.strip()

        if stripped.startswith("```"):
            return "```"
        if stripped.startswith("~~~"):
            return "~~~"

        return None

    def _new_chunk_id(self) -> str:
        return uuid4().hex
