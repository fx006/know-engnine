from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class UserModel(Base, BaseEntity):
    """认证用户表：保存账号、密码哈希和基础角色信息。"""

    __tablename__ = "auth_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_auth_user_username"),
        Index("idx_auth_user_user_id", "user_id"),
        Index("idx_auth_user_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    # 只保存哈希值，不保存明文密码；生成逻辑统一放在 core/security.py。
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
        server_default="user",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RefreshTokenModel(Base, BaseEntity):
    """刷新令牌表：支持 refresh token 撤销、过期和后续轮换。"""

    __tablename__ = "auth_refresh_token"
    __table_args__ = (
        UniqueConstraint("token_jti", name="uk_auth_refresh_token_jti"),
        UniqueConstraint("token_hash", name="uk_auth_refresh_token_hash"),
        Index("idx_auth_refresh_token_user_id", "user_id"),
        Index("idx_auth_refresh_token_status", "status"),
        Index("idx_auth_refresh_token_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # JWT payload 里的 jti，用于定位这枚 refresh token。
    token_jti: Mapped[str] = mapped_column(String(64), nullable=False)
    # refresh token 明文只返回给客户端一次，数据库保存指纹用于校验和撤销。
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    # 这里沿用项目现有风格，用逻辑 user_id 关联 auth_user.user_id。
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
