from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.dependencies.auth import get_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.models.upload import FileObjectModel, UploadSessionModel
from know_engine_py.app.schemas.upload import (
    FileObjectResponse,
    UploadChunkResponse,
    UploadCompleteResponse,
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
)
from know_engine_py.app.services.upload_session_service import (
    UploadCompleteResult,
    UploadInitResult,
    UploadSessionService,
    UploadStatusResult,
)
from know_engine_py.app.storage.base import FileStorage
from know_engine_py.app.storage.factory import create_file_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])


def get_upload_file_storage() -> FileStorage:
    """获取上传文件存储适配器。"""
    return create_file_storage()


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """初始化分片上传。

    - 若相同 hash/size 的文件对象已存在，直接返回秒传结果。
    - 否则创建 upload session，前端后续按 chunk_index 上传分片。
    """
    service = UploadSessionService(db)

    try:
        result = await service.init_upload(
            file_hash=request.file_hash,
            file_name=request.file_name,
            file_size=request.file_size,
            chunk_size=request.chunk_size,
            content_type=request.content_type,
            created_by=current_user.user_id,
        )
        await db.commit()
        return _to_init_response(
            result,
            request=request,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """查询上传会话状态，供前端恢复上传时判断缺哪些分片。"""
    service = UploadSessionService(db)

    try:
        result = await service.get_upload_status(upload_id)
        if result.upload_session.created_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="不能访问其他用户的上传会话")
        return _to_status_response(result)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{upload_id}/chunks/{chunk_index}", response_model=UploadChunkResponse)
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    file_storage: FileStorage = Depends(get_upload_file_storage),
    current_user: UserModel = Depends(get_current_user),
):
    """上传单个分片。

    分片 bytes 先写入对象存储，再记录 UploadChunkModel。
    同一个 chunk_index 重复上传时覆盖对象并幂等更新数据库记录。
    """
    service = UploadSessionService(db)

    try:
        status_before = await service.get_upload_status(upload_id)
        upload_session = status_before.upload_session
        if upload_session.created_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="不能访问其他用户的上传会话")

        content = await file.read()
        if not content:
            raise ValueError("分片内容不能为空")

        object_name = _build_chunk_object_name(
            upload_id=upload_session.upload_id,
            chunk_index=chunk_index,
        )
        await file_storage.upload_bytes(
            object_name=object_name,
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )

        upload_chunk_model = await service.mark_chunk_uploaded(
            upload_id=upload_session.upload_id,
            chunk_index=chunk_index,
            chunk_size=len(content),
            object_name=object_name,
        )
        status_after = await service.get_upload_status(upload_session.upload_id)
        await db.commit()

        return UploadChunkResponse(
            uploadId=upload_session.upload_id,
            chunkIndex=upload_chunk_model.chunk_index,
            objectName=upload_chunk_model.object_name,
            chunkSize=upload_chunk_model.chunk_size,
            uploadedChunks=status_after.upload_session.uploaded_chunks,
            uploadedChunkIndexes=status_after.uploaded_chunk_indexes,
            status=upload_chunk_model.status,
        )
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    file_storage: FileStorage = Depends(get_upload_file_storage),
    current_user: UserModel = Depends(get_current_user),
):
    """完成分片上传，合并所有 chunk 并生成完整文件对象。"""
    service = UploadSessionService(db, file_storage=file_storage)

    try:
        result = await service.complete_upload(
            upload_id=upload_id,
            completed_by=current_user.user_id,
        )
        await db.commit()
        return _to_complete_response(result)
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _to_init_response(
    result: UploadInitResult,
    *,
    request: UploadInitRequest,
) -> UploadInitResponse:
    if result.file_object is not None:
        return UploadInitResponse(
            instantUpload=True,
            uploadId=None,
            fileHash=result.file_object.file_hash,
            fileName=result.file_object.file_name,
            fileSize=result.file_object.file_size,
            chunkSize=request.chunk_size,
            totalChunks=0,
            uploadedChunks=0,
            uploadedChunkIndexes=[],
            status=result.file_object.status,
            fileObject=_to_file_object_response(result.file_object),
        )

    upload_session = _require_upload_session(result.upload_session)
    return UploadInitResponse(
        instantUpload=False,
        uploadId=upload_session.upload_id,
        fileHash=upload_session.file_hash,
        fileName=upload_session.file_name,
        fileSize=upload_session.file_size,
        chunkSize=upload_session.chunk_size,
        totalChunks=upload_session.total_chunks,
        uploadedChunks=upload_session.uploaded_chunks,
        uploadedChunkIndexes=result.uploaded_chunk_indexes or [],
        status=upload_session.status,
        fileObject=None,
    )


def _to_status_response(result: UploadStatusResult) -> UploadStatusResponse:
    upload_session = result.upload_session
    return UploadStatusResponse(
        uploadId=upload_session.upload_id,
        fileHash=upload_session.file_hash,
        fileName=upload_session.file_name,
        fileSize=upload_session.file_size,
        chunkSize=upload_session.chunk_size,
        totalChunks=upload_session.total_chunks,
        uploadedChunks=upload_session.uploaded_chunks,
        uploadedChunkIndexes=result.uploaded_chunk_indexes,
        status=upload_session.status,
        createdAt=upload_session.created_at,
        updatedAt=upload_session.updated_at,
    )


def _to_file_object_response(file_object: FileObjectModel) -> FileObjectResponse:
    return FileObjectResponse.model_validate(file_object)


def _to_complete_response(
    result: UploadCompleteResult,
) -> UploadCompleteResponse:
    return UploadCompleteResponse(
        uploadId=result.upload_session.upload_id,
        status=result.upload_session.status,
        uploadedChunks=result.upload_session.uploaded_chunks,
        uploadedChunkIndexes=result.uploaded_chunk_indexes,
        fileObject=_to_file_object_response(result.file_object),
    )


def _require_upload_session(
    upload_session: UploadSessionModel | None,
) -> UploadSessionModel:
    if upload_session is None:
        raise RuntimeError("缺少 upload_session")
    return upload_session


def _build_chunk_object_name(*, upload_id: str, chunk_index: int) -> str:
    return f"upload_chunks/{upload_id}/{chunk_index}.part"
