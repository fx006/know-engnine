from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from know_engine_py.app.models.document import KnowledgeDocumentModel, KnowledgeSegmentModel
from know_engine_py.app.models.enums import (
    DocumentStatus,
    KnowledgeBaseType,
    SegmentStatus,
)
from know_engine_py.app.rag.parsers.base import UnsupportedFileTypeError
from know_engine_py.app.rag.parsers.factory import ParserFactory
from know_engine_py.app.rag.splitters.factory import SplitterFactory
from know_engine_py.app.rag.splitters.types import DocumentSplitParam
from know_engine_py.app.storage.base import FileStorage


class DocumentProcessService:
    """文档处理编排服务。

    职责边界：
    1. 调用 parser 把原始文件 bytes 转成统一文本。
    2. 创建/更新文档记录并维护状态。
    3. 调用 splitter 生成 segments 并落库。

    说明：该服务只做 flush，不主动 commit，事务边界由调用方控制。
    """

    def __init__(
        self,
        session: AsyncSession,
        parser_factory: ParserFactory | None = None,
        file_storage: FileStorage | None = None,
    ):
        self.session = session
        self.parser_factory = parser_factory or ParserFactory()
        self.file_storage = file_storage

    async def import_document(
        self,
        *,
        file_name: str,
        content: bytes,
        doc_title: str | None = None,
        upload_user: str | None = None,
        accessible_by: str | None = None,
        description: str | None = None,
        knowledge_base_type: str = KnowledgeBaseType.DOCUMENT_SEARCH.value,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
        source_file_url: str | None = None,
        file_object_id: str | None = None,
    ) -> KnowledgeDocumentModel:
        """导入可直接解析的文本类文件：创建记录 → 解析，返回 CONVERTED 状态文档。"""
        # 这里的“上传”是创建 DB 记录；物理文件上传已由 FileStorage 完成。
        document = await self.create_uploaded_document(
            file_name=file_name,
            doc_title=doc_title,
            upload_user=upload_user,
            accessible_by=accessible_by,
            description=description,
            knowledge_base_type=knowledge_base_type,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
            source_file_url=source_file_url,
            file_object_id=file_object_id,
        )
        return await self.convert_document(
            document.doc_id,
            content=content,
            file_name=file_name,
        )


    async def split_document(
        self,
        document_id: int,
        *,
        split_param: DocumentSplitParam | None = None,
        chunk_size: int = 800,
        overlap: int = 80,
    ) -> int:
        """切分已转换文档并保存 segments。"""
        document = await self._get_document_or_raise(document_id)

        # 如果文档已经切分过，直接返回segment数量
        if document.status == DocumentStatus.CHUNKED.value:
            return await self._count_embeddable_segments(document_id)

        # 只有 CONVERTED 状态的文档才能切分
        if document.status != DocumentStatus.CONVERTED.value:
            raise ValueError(
                f"文档状态不为 {DocumentStatus.CONVERTED.value}，无法切分：{document.status}"
            )

        parsed_text = await self._load_converted_text(document)

        split_param = split_param or DocumentSplitParam(
            chunk_size=chunk_size,
            overlap=overlap,
        )
        splitter = SplitterFactory.create(split_param)
        base_metadata = {
            "docId": document.doc_id,
            "fileName": document.doc_title,
            "url": document.converted_doc_url or document.doc_url or "",
        }
        if document.accessible_by:
            base_metadata["accessibleBy"] = document.accessible_by
        if document.group_id:
            base_metadata["groupId"] = document.group_id
        if document.knowledge_base_id:
            base_metadata["knowledgeBaseId"] = document.knowledge_base_id

        split_result = splitter.split(parsed_text, base_metadata=base_metadata)

        embeddable_count = 0
        segment_models: list[KnowledgeSegmentModel] = []
        for index, segment in enumerate(split_result):
            metadata = segment.metadata or {}
            skip_embedding = 1 if metadata.get("skipEmbedding") == 1 else 0
            if skip_embedding == 0:
                embeddable_count += 1
            segment_models.append(
                KnowledgeSegmentModel(
                    text=segment.page_content,
                    chunk_id=metadata.get("chunkId"),
                    extra_metadata=metadata,
                    document_id=document.doc_id,
                    chunk_order=index,
                    embedding_id=None,
                    status=SegmentStatus.STORED.value,
                    skip_embedding=skip_embedding,
                )
            )

        if segment_models:
            self.session.add_all(segment_models)

        document.status = DocumentStatus.CHUNKED.value
        await self.session.flush()
        return embeddable_count

    async def _count_segments(self, document_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(KnowledgeSegmentModel)
            .where(KnowledgeSegmentModel.document_id == document_id)
        )
        return int(result.scalar_one())

    async def create_uploaded_document(
        self,
        *,
        file_name: str,
        doc_title: str | None = None,
        upload_user: str | None = None,
        accessible_by: str | None = None,
        description: str | None = None,
        knowledge_base_type: str = KnowledgeBaseType.DOCUMENT_SEARCH.value,
        group_id: str | None = None,
        knowledge_base_id: str | None = None,
        source_file_url: str | None = None,
        file_object_id: str | None = None,
    ) -> KnowledgeDocumentModel:
        """创建文档记录并置为 UPLOADED，不做内容解析。

        source_file_url 来自 FileStorage.upload_bytes()，不是用户请求入参。
        """
        if not file_name:
            raise ValueError("file_name 不能为空")

        # source_file_url 来自对象存储；为空时只在单测/本地文本导入中降级为 local URL。
        safe_name = Path(file_name).name
        title = doc_title or safe_name
        doc_url = source_file_url or f"local://source/{safe_name}"
        normalized_file_object_id = (file_object_id or "").strip() or None
        extension = {
            "source_file_name": safe_name,
        }
        if normalized_file_object_id:
            extension["file_object_id"] = normalized_file_object_id

        document = KnowledgeDocumentModel(
            doc_title=title,
            upload_user=upload_user,
            doc_url=doc_url,
            converted_doc_url=None,
            status=DocumentStatus.UPLOADED.value,
            accessible_by=accessible_by,
            description=description,
            knowledge_base_type=knowledge_base_type,
            group_id=group_id,
            knowledge_base_id=knowledge_base_id,
            file_object_id=normalized_file_object_id,
            extension=extension,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def convert_document(
        self,
        document_id: int,
        content: bytes,
        file_name: str | None = None,
    ) -> KnowledgeDocumentModel:
        """转换已上传文档为 CONVERTED 状态。"""
        document = await self._get_document_or_raise(document_id)
        self._ensure_status(
            current=document.status,
            allowed={DocumentStatus.UPLOADED.value},
            action="convert_document",
        )

        document.status = DocumentStatus.CONVERTING.value
        await self.session.flush()

        try:
            # 在同一个 session 中多次 flush 后需要显式标记为已修改才能生成正确的 UPDATE 语句。
            ext = document.extension or {}
            parse_name = file_name or ext.get("source_file_name") or document.doc_title

            parser = self.parser_factory.get_parser(parse_name)
            processed = parser.parse(content, parse_name)

            safe_name = Path(parse_name).name
            ext.update(
                {
                    "parse_mode": "direct_text",
                    "parser_name": parser.__class__.__name__,
                    "parsed_text": processed.text,
                    "content_type": processed.content_type,
                    "source_file_name": processed.source_file_name,
                }
            )
            document.extension = ext
            flag_modified(document, "extension")
            # txt/md 直通解析不会生成新文件，转换后 URL 复用原始存储地址。
            document.converted_doc_url = document.doc_url or f"local://converted/{safe_name}"
            document.status = DocumentStatus.CONVERTED.value
            await self.session.flush()
            return document
        except Exception:
            document.status = DocumentStatus.UPLOADED.value
            await self.session.flush()
            raise

    def supports_direct_parse(self, file_name: str) -> bool:
        """判断文件是否可以在当前进程内直接解析。"""
        try:
            self.parser_factory.get_parser(file_name)
            return True
        except UnsupportedFileTypeError:
            return False

    async def _get_document_or_raise(self, document_id: int) -> KnowledgeDocumentModel:
        result = await self.session.execute(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.doc_id == document_id
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"文档不存在：{document_id}")
        return document

    def _ensure_status(
        self,
        *,
        current: str,
        allowed: set[str],
        action: str,
    ) -> None:
        if current not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(
                f"文档当前状态为{current},不能执行{action},允许状态：{allowed_text}"
            )

    async def _count_embeddable_segments(self, document_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(KnowledgeSegmentModel)
            .where(KnowledgeSegmentModel.document_id == document_id)
            .where(KnowledgeSegmentModel.skip_embedding == 0)
        )
        return int(result.scalar_one())

    async def _load_converted_text(self, document: KnowledgeDocumentModel) -> str:
        """加载可切分文本。

        txt/md 直通解析会把文本放在 extension.parsed_text；
        MinerU 解析后的 Markdown 则从 converted_doc_url 指向的对象存储读取。
        """
        extension = document.extension or {}
        parsed_text = extension.get("parsed_text")
        if isinstance(parsed_text, str) and parsed_text.strip():
            return parsed_text

        if self.file_storage is None or not document.converted_doc_url:
            raise ValueError("文档缺少可切分文本")

        # MinerU 转换后的 Markdown 保存在对象存储，切分时按 URL 反解并下载。
        object_name = self.file_storage.extract_object_name(document.converted_doc_url)
        content = await self.file_storage.download_bytes(object_name)

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("转换后的文档不是 UTF-8 文本") from exc

        if not text.strip():
            raise ValueError("文档缺少可切分文本")

        return text
