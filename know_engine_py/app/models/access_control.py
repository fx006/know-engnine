from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class GroupModel(Base, BaseEntity):
    """企业空间/群组表：承载知识库和成员权限边界。"""

    __tablename__ = "access_group"
    __table_args__ = (
        UniqueConstraint("group_id", name="uk_access_group_group_id"),
        Index("idx_access_group_owner_user_id", "owner_user_id"),
        Index("idx_access_group_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )


class GroupMemberModel(Base, BaseEntity):
    """群组成员表：描述用户在某个 group 内的角色。"""

    __tablename__ = "access_group_member"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uk_group_member_group_user"),
        Index("idx_group_member_user_id", "user_id"),
        Index("idx_group_member_group_id", "group_id"),
        Index("idx_group_member_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )


class KnowledgeBaseModel(Base, BaseEntity):
    """知识库表：文档、segment 和检索权限的归属单元。"""

    __tablename__ = "knowledge_base"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            name="uk_knowledge_base_knowledge_base_id",
        ),
        Index("idx_knowledge_base_group_id", "group_id"),
        Index("idx_knowledge_base_created_by", "created_by"),
        Index("idx_knowledge_base_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="group",
        server_default="group",
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
