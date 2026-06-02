from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupCreateRequest(BaseModel):
    """创建群组请求。"""

    model_config = ConfigDict(populate_by_name=True)

    group_name: str = Field(alias="groupName")
    description: str | None = None


class GroupResponse(BaseModel):
    """群组响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    group_id: str = Field(alias="groupId")
    group_name: str = Field(alias="groupName")
    owner_user_id: str = Field(alias="ownerUserId")
    description: str | None = None
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class GroupMemberAddRequest(BaseModel):
    """添加成员请求。"""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    role: str = "group_member"


class GroupMemberUpdateRequest(BaseModel):
    """修改成员角色请求。"""

    role: str


class GroupMemberResponse(BaseModel):
    """群组成员响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    group_id: str = Field(alias="groupId")
    user_id: str = Field(alias="userId")
    role: str
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求。"""

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId")
    name: str
    description: str | None = None
    visibility: str = "group"


class KnowledgeBaseUpdateRequest(BaseModel):
    """更新知识库请求。"""

    name: str | None = None
    description: str | None = None
    visibility: str | None = None


class KnowledgeBaseResponse(BaseModel):
    """知识库响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    knowledge_base_id: str = Field(alias="knowledgeBaseId")
    group_id: str = Field(alias="groupId")
    name: str
    description: str | None = None
    visibility: str
    created_by: str = Field(alias="createdBy")
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
