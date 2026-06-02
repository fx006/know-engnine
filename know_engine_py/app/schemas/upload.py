from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadInitRequest(BaseModel):
    """初始化分片上传请求。"""

    model_config = ConfigDict(populate_by_name=True)

    file_hash: str = Field(alias="fileHash")
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize", gt=0)
    chunk_size: int = Field(alias="chunkSize", gt=0)
    content_type: str | None = Field(default=None, alias="contentType")


class FileObjectResponse(BaseModel):
    """已完成文件对象响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    file_object_id: str = Field(alias="fileObjectId")
    file_hash: str = Field(alias="fileHash")
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize")
    object_name: str = Field(alias="objectName")
    file_url: str = Field(alias="fileUrl")
    content_type: str | None = Field(default=None, alias="contentType")
    status: str
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UploadInitResponse(BaseModel):
    """初始化上传响应：秒传命中或新建 upload session。"""

    model_config = ConfigDict(populate_by_name=True)

    instant_upload: bool = Field(alias="instantUpload")
    upload_id: str | None = Field(default=None, alias="uploadId")
    file_hash: str = Field(alias="fileHash")
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize")
    chunk_size: int = Field(alias="chunkSize")
    total_chunks: int = Field(alias="totalChunks")
    uploaded_chunks: int = Field(alias="uploadedChunks")
    uploaded_chunk_indexes: list[int] = Field(alias="uploadedChunkIndexes")
    status: str
    file_object: FileObjectResponse | None = Field(default=None, alias="fileObject")


class UploadStatusResponse(BaseModel):
    """上传会话状态响应，用于断点续传查询。"""

    model_config = ConfigDict(populate_by_name=True)

    upload_id: str = Field(alias="uploadId")
    file_hash: str = Field(alias="fileHash")
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize")
    chunk_size: int = Field(alias="chunkSize")
    total_chunks: int = Field(alias="totalChunks")
    uploaded_chunks: int = Field(alias="uploadedChunks")
    uploaded_chunk_indexes: list[int] = Field(alias="uploadedChunkIndexes")
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UploadChunkResponse(BaseModel):
    """上传分片响应。"""

    model_config = ConfigDict(populate_by_name=True)

    upload_id: str = Field(alias="uploadId")
    chunk_index: int = Field(alias="chunkIndex")
    object_name: str = Field(alias="objectName")
    chunk_size: int = Field(alias="chunkSize")
    uploaded_chunks: int = Field(alias="uploadedChunks")
    uploaded_chunk_indexes: list[int] = Field(alias="uploadedChunkIndexes")
    status: str


class UploadCompleteResponse(BaseModel):
    """完成分片上传响应。"""

    model_config = ConfigDict(populate_by_name=True)

    upload_id: str = Field(alias="uploadId")
    status: str
    uploaded_chunks: int = Field(alias="uploadedChunks")
    uploaded_chunk_indexes: list[int] = Field(alias="uploadedChunkIndexes")
    file_object: FileObjectResponse = Field(alias="fileObject")
