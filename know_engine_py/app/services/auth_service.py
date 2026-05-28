from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.models.auth import RefreshTokenModel, UserModel


@dataclass(slots=True)
class AuthTokenPair:
    """登录或刷新后返回给 API 层的认证结果。"""

    access_token: str
    refresh_token: str
    # access_token 的有效秒数，方便前端设置定时刷新
    expires_in: int
    user: UserModel
    token_type: str = "bearer"


class AuthService:
    """认证业务服务。

    负责注册、登录、refresh token 轮换、退出和当前用户查询。
    该服务只 flush，不主动 commit；事务边界由 API 层控制。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
    ):
        self.session = session
        self.settings = settings or get_settings()

    async def register(
        self,
        *,
        username: str,
        password: str,
        nickname: str | None = None,
        role: str = "user",
    ) -> UserModel:
        """注册用户，密码只保存哈希值。"""
        normalized_username = self._normalize_required(username, "用户名")
        self._validate_password(password)

        existing_user = await self.get_by_username(normalized_username)
        if existing_user is not None:
            raise ValueError("用户名已存在")

        user = UserModel(
            user_id=uuid4().hex,
            username=normalized_username,
            password_hash=hash_password(password),
            nickname=nickname.strip() if nickname and nickname.strip() else None,
            role=role,
            status="active",
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def login(self, *, username: str, password: str) -> AuthTokenPair:
        """校验用户名密码，成功后签发 access/refresh token。"""
        normalized_username = self._normalize_required(username, "用户名")
        user = await self.get_by_username(normalized_username)

        if user is None or user.status != "active":
            raise ValueError("用户名或密码错误")

        if not verify_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")

        user.last_login_at = datetime.now(UTC)
        token_pair = await self._issue_token_pair(user)
        await self.session.flush()
        await self.session.refresh(user)
        return token_pair

    async def refresh(self, refresh_token: str) -> AuthTokenPair:
        """使用 refresh token 换取新 token，并撤销旧 refresh token。"""
        payload = decode_token(
            refresh_token,
            expected_type="refresh",
            settings=self.settings,
        )
        token_record = await self._get_refresh_token_by_hash(refresh_token)
        if token_record is None or token_record.token_jti != payload["jti"]:
            raise ValueError("refresh token 不存在")

        if token_record.status != "active" or token_record.revoked_at is not None:
            raise ValueError("refresh token 已失效")

        if self._is_expired(token_record.expires_at):
            raise ValueError("refresh token 已过期")

        user = await self.get_by_user_id(str(payload["sub"]))
        if user is None or user.status != "active":
            raise ValueError("用户不存在或已禁用")

        new_token_pair = await self._issue_token_pair(user)
        new_payload = decode_token(
            new_token_pair.refresh_token,
            expected_type="refresh",
            settings=self.settings,
        )

        # refresh token 采用轮换策略：旧 token 用过即撤销，降低泄露后的复用风险。
        token_record.status = "revoked"
        token_record.revoked_at = datetime.now(UTC)
        token_record.used_at = token_record.revoked_at
        token_record.replaced_by_jti = str(new_payload["jti"])
        await self.session.flush()
        await self.session.refresh(user)
        return new_token_pair

    async def logout(self, refresh_token: str) -> RefreshTokenModel:
        """退出登录：撤销当前 refresh token。"""
        payload = decode_token(
            refresh_token,
            expected_type="refresh",
            settings=self.settings,
        )
        token_record = await self._get_refresh_token_by_hash(refresh_token)
        if token_record is None or token_record.token_jti != payload["jti"]:
            raise ValueError("refresh token 不存在")

        if token_record.status == "active":
            token_record.status = "revoked"
            token_record.revoked_at = datetime.now(UTC)
            await self.session.flush()

        return token_record

    async def get_current_user(self, access_token: str) -> UserModel:
        """从 access token 解析当前用户，并确认用户仍然有效。"""
        payload = decode_token(
            access_token,
            expected_type="access",
            settings=self.settings,
        )

        user = await self.get_by_user_id(str(payload["sub"]))
        if user is None or user.status != "active":
            raise ValueError("用户不存在或已禁用")

        return user

    async def get_by_username(self, username: str) -> UserModel | None:
        """按用户名查询用户。"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> UserModel | None:
        """按业务 user_id 查询用户。"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _issue_token_pair(self, user: UserModel) -> AuthTokenPair:
        refresh_jti = uuid4().hex
        access_token = create_access_token(
            user_id=user.user_id,
            role=user.role,
            settings=self.settings,
        )
        refresh_token = create_refresh_token(
            user_id=user.user_id,
            role=user.role,
            token_jti=refresh_jti,
            settings=self.settings,
        )

        refresh_payload = decode_token(
            refresh_token,
            expected_type="refresh",
            settings=self.settings,
        )
        token_record = RefreshTokenModel(
            token_jti=str(refresh_payload["jti"]),
            token_hash=hash_token(refresh_token),
            user_id=user.user_id,
            status="active",
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=UTC),
        )
        self.session.add(token_record)

        return AuthTokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
            user=user,
        )

    async def _get_refresh_token_by_hash(
        self,
        refresh_token: str,
    ) -> RefreshTokenModel | None:
        result = await self.session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_hash == hash_token(refresh_token)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized = value.strip() if value else ""
        if not normalized:
            raise ValueError(f"{field_name}不能为空")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if not password or not password.strip():
            raise ValueError("密码不能为空")
        if len(password) < 8:
            raise ValueError("密码长度不能小于 8 位")

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return expires_at <= now
