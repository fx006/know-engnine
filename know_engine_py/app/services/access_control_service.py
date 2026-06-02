from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.access_control import (
    GroupMemberModel,
    GroupModel,
    KnowledgeBaseModel,
)
from know_engine_py.app.models.enums import GroupRole, KnowledgeBaseVisibility


class AccessControlService:
    """群组和知识库权限服务。

    负责企业空间、成员角色和知识库归属管理；只 flush，不主动 commit。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_group(
        self,
        *,
        group_name: str,
        owner_user_id: str,
        description: str | None = None,
    ) -> GroupModel:
        """创建群组，并自动把创建者加入为 group_owner。"""
        normalized_name = self._normalize_required(group_name, "群组名称")
        normalized_owner = self._normalize_required(owner_user_id, "owner_user_id")

        group = GroupModel(
            group_id=uuid4().hex,
            group_name=normalized_name,
            owner_user_id=normalized_owner,
            description=description.strip() if description and description.strip() else None,
            status="active",
        )
        self.session.add(group)
        await self.session.flush()

        owner_member = GroupMemberModel(
            group_id=group.group_id,
            user_id=normalized_owner,
            role=GroupRole.GROUP_OWNER.value,
            status="active",
        )
        self.session.add(owner_member)
        await self.session.flush()
        await self.session.refresh(group)
        return group

    async def add_member(
        self,
        *,
        group_id: str,
        user_id: str,
        role: str,
        operator_user_id: str,
    ) -> GroupMemberModel:
        """添加群组成员，只有群主或系统管理员可操作。"""
        normalized_group_id = self._normalize_required(group_id, "group_id")
        normalized_user_id = self._normalize_required(user_id, "user_id")
        normalized_operator = self._normalize_required(
            operator_user_id,
            "operator_user_id",
        )
        normalized_role = self._normalize_role(role)

        await self._assert_group_exists(normalized_group_id)
        if not await self.can_manage_members(
            group_id=normalized_group_id,
            user_id=normalized_operator,
        ):
            raise ValueError("没有群组成员管理权限")

        existing_member = await self.get_member(
            group_id=normalized_group_id,
            user_id=normalized_user_id,
        )
        if existing_member is not None:
            existing_member.role = normalized_role
            existing_member.status = "active"
            await self.session.flush()
            await self.session.refresh(existing_member)
            return existing_member

        member = GroupMemberModel(
            group_id=normalized_group_id,
            user_id=normalized_user_id,
            role=normalized_role,
            status="active",
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def list_members(self, group_id: str) -> list[GroupMemberModel]:
        """查询群组成员。"""
        result = await self.session.execute(
            select(GroupMemberModel)
            .where(GroupMemberModel.group_id == group_id)
            .where(GroupMemberModel.status == "active")
            .order_by(GroupMemberModel.id.asc())
        )
        return list(result.scalars().all())

    async def update_member_role(
        self,
        *,
        group_id: str,
        user_id: str,
        role: str,
        operator_user_id: str,
    ) -> GroupMemberModel:
        """修改成员角色。"""
        normalized_role = self._normalize_role(role)
        if not await self.can_manage_members(
            group_id=group_id,
            user_id=operator_user_id,
        ):
            raise ValueError("没有群组成员管理权限")

        member = await self.get_member(group_id=group_id, user_id=user_id)
        if member is None:
            raise ValueError("群组成员不存在")

        member.role = normalized_role
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def create_knowledge_base(
        self,
        *,
        group_id: str,
        name: str,
        created_by: str,
        visibility: str = KnowledgeBaseVisibility.GROUP.value,
        description: str | None = None,
    ) -> KnowledgeBaseModel:
        """创建知识库；创建人必须是群组成员。"""
        normalized_group_id = self._normalize_required(group_id, "group_id")
        normalized_name = self._normalize_required(name, "知识库名称")
        normalized_creator = self._normalize_required(created_by, "created_by")
        normalized_visibility = self._normalize_visibility(visibility)

        await self._assert_group_exists(normalized_group_id)
        if not await self.is_group_member(
            group_id=normalized_group_id,
            user_id=normalized_creator,
        ):
            raise ValueError("用户不是群组成员")

        knowledge_base = KnowledgeBaseModel(
            knowledge_base_id=uuid4().hex,
            group_id=normalized_group_id,
            name=normalized_name,
            description=description.strip() if description and description.strip() else None,
            visibility=normalized_visibility,
            created_by=normalized_creator,
            status="active",
        )
        self.session.add(knowledge_base)
        await self.session.flush()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def list_user_knowledge_bases(
        self,
        user_id: str,
    ) -> list[KnowledgeBaseModel]:
        """查询用户所在群组下可见的知识库。"""
        result = await self.session.execute(
            select(KnowledgeBaseModel)
            .join(
                GroupMemberModel,
                KnowledgeBaseModel.group_id == GroupMemberModel.group_id,
            )
            .where(GroupMemberModel.user_id == user_id)
            .where(GroupMemberModel.status == "active")
            .where(KnowledgeBaseModel.status == "active")
            .order_by(KnowledgeBaseModel.id.asc())
        )
        return list(result.scalars().all())

    async def update_knowledge_base(
        self,
        *,
        knowledge_base_id: str,
        operator_user_id: str,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> KnowledgeBaseModel:
        """更新知识库基础信息；只有群组管理者可操作。"""
        knowledge_base = await self.get_knowledge_base(knowledge_base_id)
        if knowledge_base is None:
            raise ValueError("知识库不存在")

        if not await self.can_manage_members(
            group_id=knowledge_base.group_id,
            user_id=operator_user_id,
        ):
            raise ValueError("没有知识库管理权限")

        if name is not None:
            knowledge_base.name = self._normalize_required(name, "知识库名称")
        if description is not None:
            knowledge_base.description = (
                description.strip() if description.strip() else None
            )
        if visibility is not None:
            knowledge_base.visibility = self._normalize_visibility(visibility)

        await self.session.flush()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def get_member(
        self,
        *,
        group_id: str,
        user_id: str,
    ) -> GroupMemberModel | None:
        """查询单个群组成员。"""
        result = await self.session.execute(
            select(GroupMemberModel)
            .where(GroupMemberModel.group_id == group_id)
            .where(GroupMemberModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_knowledge_base(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBaseModel | None:
        """按知识库 ID 查询知识库。"""
        result = await self.session.execute(
            select(KnowledgeBaseModel).where(
                KnowledgeBaseModel.knowledge_base_id == knowledge_base_id
            )
        )
        return result.scalar_one_or_none()

    async def is_group_member(self, *, group_id: str, user_id: str) -> bool:
        """判断用户是否是群组有效成员。"""
        member = await self.get_member(group_id=group_id, user_id=user_id)
        return member is not None and member.status == "active"

    async def can_manage_members(self, *, group_id: str, user_id: str) -> bool:
        """判断用户是否可管理群组成员和知识库配置。"""
        member = await self.get_member(group_id=group_id, user_id=user_id)
        if member is None or member.status != "active":
            return False
        return member.role in {
            GroupRole.SYSTEM_ADMIN.value,
            GroupRole.GROUP_OWNER.value,
        }

    async def _assert_group_exists(self, group_id: str) -> None:
        result = await self.session.execute(
            select(GroupModel)
            .where(GroupModel.group_id == group_id)
            .where(GroupModel.status == "active")
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("群组不存在")

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized = value.strip() if value else ""
        if not normalized:
            raise ValueError(f"{field_name}不能为空")
        return normalized

    @staticmethod
    def _normalize_role(role: str) -> str:
        normalized = AccessControlService._normalize_required(role, "角色")
        allowed = {item.value for item in GroupRole}
        if normalized not in allowed:
            raise ValueError("非法群组角色")
        return normalized

    @staticmethod
    def _normalize_visibility(visibility: str) -> str:
        normalized = AccessControlService._normalize_required(visibility, "可见性")
        allowed = {item.value for item in KnowledgeBaseVisibility}
        if normalized not in allowed:
            raise ValueError("非法知识库可见性")
        return normalized
