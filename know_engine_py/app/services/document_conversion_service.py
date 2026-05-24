from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from know_engine_py.app.models.document import KnowledgeDocumentModel
from know_engine_py.app.models.enums import DocumentStatus
from know_engine_py.app.rag.parsers.mineru_client import MinerUClient
from know_engine_py.app.storage.base import FileStorage


class DocumentConversionService:
    """文档转换编排服务。

    用于 Celery worker 侧把 PDF/Word 等非直通文件转换成 Markdown。
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        file_storage: FileStorage,
        mineru_client: MinerUClient,
    ):
        self.session = session
        self.file_storage = file_storage
        self.mineru_client = mineru_client

    async def convert_document_to_markdown(self, document_id: int) -> KnowledgeDocumentModel:
        """把 UPLOADED 文档转换为 Markdown，并推进到 CONVERTED。"""
        document = await self._get_document_or_raise(document_id)

        if document.status == DocumentStatus.CONVERTED.value:
            return document

        if document.status != DocumentStatus.UPLOADED.value:
            raise ValueError(
                f"文档状态不为 {DocumentStatus.UPLOADED.value}，无法转换：{document.status}"
            )

        if not document.doc_url:
            raise ValueError("文档缺少原始文件地址，无法转换")

        document.status = DocumentStatus.CONVERTING.value
        await self.session.flush()

        try:
            # Worker 不能拿到 HTTP 上传时的 UploadFile，只能通过 doc_url 回读对象存储。
            object_name = self.file_storage.extract_object_name(document.doc_url)
            source_content = await self.file_storage.download_bytes(object_name)

            source_file_name = self._resolve_source_file_name(document)
            parsed = await self.mineru_client.parse_to_markdown(
                file_name=source_file_name,
                content=source_content,
            )

            converted_object_name = self._build_converted_object_name(
                document_id=document.doc_id,
                source_file_name=source_file_name,
            )
            # 转换后的 Markdown 也放对象存储，DB 只保存 URL；避免把大文本塞进 JSON 字段。
            converted_url = await self.file_storage.upload_bytes(
                object_name=converted_object_name,
                content=parsed.markdown.encode("utf-8"),
                content_type="text/markdown",
            )

            extension = dict(document.extension or {})
            extension.update(
                {
                    "parse_mode": "mineru_markdown",
                    "parser_name": "MinerUClient",
                    "source_file_name": source_file_name,
                    "converted_file_name": Path(converted_object_name).name,
                    "mineru_response": self._summarize_mineru_response(
                        parsed.raw_response
                    ),
                }
            )

            document.extension = extension
            flag_modified(document, "extension")
            document.converted_doc_url = converted_url
            document.status = DocumentStatus.CONVERTED.value
            await self.session.flush()
            return document
        except Exception:
            # 转换失败允许后续重试，所以回到 UPLOADED，而不是停在 CONVERTING。
            document.status = DocumentStatus.UPLOADED.value
            await self.session.flush()
            raise

    async def _get_document_or_raise(
        self,
        document_id: int,
    ) -> KnowledgeDocumentModel:
        result = await self.session.execute(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.doc_id == document_id
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"文档不存在：{document_id}")
        return document

    def _resolve_source_file_name(self, document: KnowledgeDocumentModel) -> str:
        extension = document.extension or {}
        source_file_name = extension.get("source_file_name")
        if isinstance(source_file_name, str) and source_file_name.strip():
            return source_file_name

        return document.doc_title

    def _build_converted_object_name(
        self,
        *,
        document_id: int,
        source_file_name: str,
    ) -> str:
        stem = Path(source_file_name).stem or f"document-{document_id}"
        return f"converted/{document_id}-{stem}.md"

    def _summarize_mineru_response(
        self,
        raw_response: dict[str, Any],
    ) -> dict[str, Any]:
        results = raw_response.get("results")
        if not isinstance(results, dict):
            return {"result_count": 0, "file_names": []}

        return {
            "result_count": len(results),
            "file_names": list(results.keys()),
        }
