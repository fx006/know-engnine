from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.dependencies.auth import get_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.schemas.access_control import (
    GroupCreateRequest,
    GroupMemberAddRequest,
    GroupMemberResponse,
    GroupMemberUpdateRequest,
    GroupResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from know_engine_py.app.services.access_control_service import AccessControlService

router = APIRouter(tags=["access-control"])


@router.post("/groups", response_model=GroupResponse)
async def create_group(
    request: GroupCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """创建群组，当前用户自动成为群主。"""
    service = AccessControlService(db)

    try:
        group = await service.create_group(
            group_name=request.group_name,
            owner_user_id=current_user.user_id,
            description=request.description,
        )
        await db.commit()
        return group
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/groups/{group_id}/members", response_model=GroupMemberResponse)
async def add_group_member(
    group_id: str,
    request: GroupMemberAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """添加群组成员。"""
    service = AccessControlService(db)

    try:
        member = await service.add_member(
            group_id=group_id,
            user_id=request.user_id,
            role=request.role,
            operator_user_id=current_user.user_id,
        )
        await db.commit()
        return member
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """查询群组成员；只有群组成员可查看。"""
    service = AccessControlService(db)

    if not await service.is_group_member(
        group_id=group_id,
        user_id=current_user.user_id,
    ):
        raise HTTPException(status_code=403, detail="用户不是群组成员")

    return await service.list_members(group_id)


@router.put(
    "/groups/{group_id}/members/{user_id}",
    response_model=GroupMemberResponse,
)
async def update_group_member_role(
    group_id: str,
    user_id: str,
    request: GroupMemberUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """修改群组成员角色。"""
    service = AccessControlService(db)

    try:
        member = await service.update_member_role(
            group_id=group_id,
            user_id=user_id,
            role=request.role,
            operator_user_id=current_user.user_id,
        )
        await db.commit()
        return member
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """创建知识库。"""
    service = AccessControlService(db)

    try:
        knowledge_base = await service.create_knowledge_base(
            group_id=request.group_id,
            name=request.name,
            description=request.description,
            visibility=request.visibility,
            created_by=current_user.user_id,
        )
        await db.commit()
        return knowledge_base
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """查询当前用户所在群组下的知识库。"""
    service = AccessControlService(db)
    return await service.list_user_knowledge_bases(current_user.user_id)


@router.put("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    knowledge_base_id: str,
    request: KnowledgeBaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """更新知识库基础信息。"""
    service = AccessControlService(db)

    try:
        knowledge_base = await service.update_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            operator_user_id=current_user.user_id,
            name=request.name,
            description=request.description,
            visibility=request.visibility,
        )
        await db.commit()
        return knowledge_base
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
