from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.document import KnowledgeSegmentModel
from know_engine_py.app.models.enums import KnowledgeBaseType
from know_engine_py.app.schemas.document import (
    DocumentResponse,
    DocumentSplitRequest,
    SegmentResponse,
)
from know_engine_py.app.services.document_process_service import DocumentProcessService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/import", response_model=DocumentResponse)
async def import_document(
    file: UploadFile = File(...),
    upload_user: str | None = Form(default=None, alias="uploadUser"),
    doc_title: str | None = Form(default=None, alias="docTitle"),
    accessible_by: str | None = Form(default=None, alias="accessibleBy"),
    description: str | None = Form(default=None),
    knowledge_base_type: str = Form(
        default=KnowledgeBaseType.DOCUMENT_SEARCH.value,
        alias="knowledgeBaseType",
    ),
    db: AsyncSession = Depends(get_db),
):
    """导入文档并完成 txt/md 直通解析。"""
    service = DocumentProcessService(db)
    content = await file.read()

    try:
        document = await service.import_document(
            file_name=file.filename or "unknown",
            content=content,
            doc_title=doc_title,
            upload_user=upload_user,
            accessible_by=accessible_by,
            description=description,
            knowledge_base_type=knowledge_base_type,
        )
        await db.commit()
        return document
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{document_id}/split")
async def split_document(
    document_id: int,
    request: DocumentSplitRequest,
    db: AsyncSession = Depends(get_db),
):
    """按指定策略切分文档，返回可向量化 segment 数量。"""
    service = DocumentProcessService(db)

    try:
        segment_count = await service.split_document(
            document_id,
            split_param=request.to_split_param(),
        )
        await db.commit()
        return {"documentId": document_id, "segmentCount": segment_count}
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
