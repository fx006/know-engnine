from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.dependencies.auth import get_optional_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.models.document import KnowledgeSegmentModel
from know_engine_py.app.models.enums import FileObjectStatus, KnowledgeBaseType
from know_engine_py.app.models.upload import FileObjectModel
from know_engine_py.app.schemas.document import (
    DocumentResponse,
    DocumentSplitRequest,
    SegmentResponse,
    DocumentSplitResponse,
    DocumentImportResponse,
)
from know_engine_py.app.services.document_process_service import DocumentProcessService
from know_engine_py.app.services.access_control_service import AccessControlService
from know_engine_py.app.storage.base import FileStorage
from know_engine_py.app.storage.factory import create_file_storage
from know_engine_py.app.tasks.document_tasks import (
    enqueue_document_conversion,
    enqueue_document_indexing,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_file_storage() -> FileStorage:
    """获取文件存储适配器。"""
    return create_file_storage()


def _build_source_object_name(file_name: str) -> str:
    """生成原始上传文件在对象存储中的 object name。"""
    safe_name = Path(file_name).name or "unknown"
    return f"source/{uuid4().hex}-{safe_name}"


@router.post("/import", response_model=DocumentImportResponse)
async def import_document(
    file: UploadFile | None = File(default=None),
    file_object_id: str | None = Form(default=None, alias="fileObjectId"),
    upload_user: str | None = Form(default=None, alias="uploadUser"),
    doc_title: str | None = Form(default=None, alias="docTitle"),
    accessible_by: str | None = Form(default=None, alias="accessibleBy"),
    knowledge_base_id: str | None = Form(default=None, alias="knowledgeBaseId"),
    description: str | None = Form(default=None),
    knowledge_base_type: str = Form(
        default=KnowledgeBaseType.DOCUMENT_SEARCH.value,
        alias="knowledgeBaseType",
    ),
    db: AsyncSession = Depends(get_db),
    file_storage: FileStorage = Depends(get_file_storage),
    current_user: UserModel | None = Depends(get_optional_current_user),
):
    """导入文档。

    支持两条入口：
    1. quick import：小文件直接 multipart 上传。
    2. resumable import：分片上传 complete 后，按 fileObjectId 导入知识库。
    """
    service = DocumentProcessService(db)

    try:
        if current_user is None:
            raise HTTPException(status_code=401, detail="请先登录后再上传文档")

        normalized_knowledge_base_id = (knowledge_base_id or "").strip()
        if not normalized_knowledge_base_id:
            raise ValueError("knowledgeBaseId 不能为空")

        access_service = AccessControlService(db)
        knowledge_base = await access_service.get_knowledge_base(
            normalized_knowledge_base_id
        )
        if knowledge_base is None or knowledge_base.status != "active":
            raise ValueError("知识库不存在")
        if not await access_service.is_group_member(
            group_id=knowledge_base.group_id,
            user_id=current_user.user_id,
        ):
            raise ValueError("用户不是知识库所属群组成员")

        group_id = knowledge_base.group_id
        normalized_file_object_id = (file_object_id or "").strip()
        if file is None and not normalized_file_object_id:
            raise ValueError("file 和 fileObjectId 不能同时为空")
        if file is not None and normalized_file_object_id:
            raise ValueError("file 和 fileObjectId 不能同时传")

        content: bytes | None = None
        source_file_url: str
        source_file_object_id: str | None = None

        if normalized_file_object_id:
            file_object = await _get_active_file_object(
                db,
                normalized_file_object_id,
            )
            file_name = file_object.file_name
            source_file_url = file_object.file_url
            source_file_object_id = file_object.file_object_id

            if service.supports_direct_parse(file_name):
                # FileObject 已经是完整文件，直通解析只需要从对象存储下载原始 bytes。
                content = await file_storage.download_bytes(file_object.object_name)
        else:
            if file is None:
                raise ValueError("file 和 fileObjectId 不能同时为空")

            content = await file.read()
            if not content:
                raise ValueError("文件内容不能为空")

            file_name = file.filename or "unknown"
            object_name = _build_source_object_name(file_name)
            # quick import 必须先保存原始文件；后续 worker 只能通过 doc_url 重新下载文件。
            source_file_url = await file_storage.upload_bytes(
                object_name=object_name,
                content=content,
                content_type=file.content_type or "application/octet-stream",
            )

        needs_conversion = False

        if service.supports_direct_parse(file_name):
            if content is None:
                raise ValueError("可直接解析的文件缺少原始内容")
            # txt/md 可在 Web 进程内直接解析，导入后立即进入 CONVERTED。
            document = await service.import_document(
                file_name=file_name,
                content=content,
                doc_title=doc_title,
                upload_user=current_user.user_id,
                accessible_by=accessible_by,
                description=description,
                knowledge_base_type=knowledge_base_type,
                group_id=group_id,
                knowledge_base_id=normalized_knowledge_base_id,
                source_file_url=source_file_url,
                file_object_id=source_file_object_id,
            )
        else:
            # PDF/Word 等慢解析文件只建 UPLOADED 记录，commit 后再投递 MinerU 转换任务。
            document = await service.create_uploaded_document(
                file_name=file_name,
                doc_title=doc_title,
                upload_user=current_user.user_id,
                accessible_by=accessible_by,
                description=description,
                knowledge_base_type=knowledge_base_type,
                group_id=group_id,
                knowledge_base_id=normalized_knowledge_base_id,
                source_file_url=source_file_url,
                file_object_id=source_file_object_id,
            )
            needs_conversion = True

        await db.commit()

        conversion_task_id: str | None = None
        conversion_queued = False
        conversion_queue_error: str | None = None

        if needs_conversion:
            try:
                # 必须在 commit 成功后投递任务，避免 worker 查不到刚创建的文档记录。
                conversion_task_id = enqueue_document_conversion(document.doc_id)
                conversion_queued = True
            except Exception as exc:
                # 文档记录已经保存成功；投递失败先返回错误，后续由转换补偿任务兜底。
                conversion_queue_error = str(exc)

        return DocumentImportResponse.model_validate(document).model_copy(
            update={
                "conversion_queued": conversion_queued,
                "conversion_task_id": conversion_task_id,
                "conversion_queue_error": conversion_queue_error,
            }
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _get_active_file_object(
    db: AsyncSession,
    file_object_id: str,
) -> FileObjectModel:
    """读取已完成上传的文件对象。

    文件对象只代表“物理文件已存在”，真正的知识库访问权限仍由 import 时的
    knowledgeBaseId 校验决定；这样既保留秒传复用，也不绕过知识库权限。
    """
    result = await db.execute(
        select(FileObjectModel).where(
            FileObjectModel.file_object_id == file_object_id
        )
    )
    file_object = result.scalar_one_or_none()
    if file_object is None:
        raise ValueError("文件对象不存在")
    if file_object.status != FileObjectStatus.ACTIVE.value:
        raise ValueError("文件对象不可用")
    return file_object


@router.post("/{document_id}/split",response_model=DocumentSplitResponse)
async def split_document(
    document_id: int,
    request: DocumentSplitRequest,
    db: AsyncSession = Depends(get_db),
    file_storage: FileStorage=Depends(get_file_storage)
):
    """按指定策略切分文档，返回可向量化 segment 数量。"""
    service = DocumentProcessService(db,file_storage=file_storage)

    try:
        segment_count = await service.split_document(
            document_id,
            split_param=request.to_split_param(),
        )
        await db.commit()

        index_task_id: str | None = None
        index_queued = False
        index_queue_error: str | None = None

        try:
            # 必须在 commit 成功后投递任务，避免 worker 查不到刚落库的 segments。
            index_task_id = enqueue_document_indexing(document_id)
            index_queued = True
        except Exception as exc:
            # 切分已经成功提交; 投递失败，后续补偿任务会扫描 CHUNKED 文档
            index_queue_error = str(exc)

        return DocumentSplitResponse(
            document_id=document_id,
            segment_count=segment_count,
            index_queued=index_queued,
            index_task_id=index_task_id,
            index_queue_error=index_queue_error
        )

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{document_id}/segments",
    response_model=list[SegmentResponse],
    response_model_by_alias=False,
)
async def list_document_segments(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """查询指定文档的切分结果。"""
    result = await db.execute(
        select(KnowledgeSegmentModel)
        .where(KnowledgeSegmentModel.document_id == document_id)
        .order_by(KnowledgeSegmentModel.chunk_order)
    )
    return list(result.scalars().all())
