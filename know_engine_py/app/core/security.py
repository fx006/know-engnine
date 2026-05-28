from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from know_engine_py.app.core.settings import Settings, get_settings

TokenType = Literal["access", "refresh"]

_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """对登录密码做不可逆哈希，数据库只保存哈希值。"""
    if not plain_password:
        raise ValueError("密码不能为空")

    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码和数据库中的密码哈希是否匹配。"""
    if not plain_password or not password_hash:
        return False

    return _password_hash.verify(plain_password, password_hash)


def hash_token(token: str) -> str:
    """生成 refresh token 指纹。

    refresh token 是可登录凭证，不能明文入库；这里存 SHA-256 指纹用于查找和撤销。
    """
    if not token:
        raise ValueError("token 不能为空")

    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: str,
    role: str | None = None,
    settings: Settings | None = None,
) -> str:
    """签发短期 access token，后续用于访问受保护接口。"""
    auth_settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=auth_settings.jwt_access_token_expire_minutes
    )

    return _create_token(
        token_type="access",
        user_id=user_id,
        expires_at=expires_at,
        role=role,
        settings=auth_settings,
    )


def create_refresh_token(
    *,
    user_id: str,
    role: str | None = None,
    token_jti: str | None = None,
    settings: Settings | None = None,
) -> str:
    """签发长期 refresh token，后续用于换取新的 access token。"""
    auth_settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        days=auth_settings.jwt_refresh_token_expire_days
    )

    return _create_token(
        token_type="refresh",
        user_id=user_id,
        expires_at=expires_at,
        role=role,
        token_jti=token_jti,
        settings=auth_settings,
    )


def decode_token(
    token: str,
    *,
    expected_type: TokenType | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """解析 JWT，并可校验它是 access token 还是 refresh token。"""
    auth_settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise ValueError("token 已过期") from exc
    except InvalidTokenError as exc:
        raise ValueError("无效 token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise ValueError("token 类型不匹配")

    if not payload.get("sub"):
        raise ValueError("token 缺少用户标识")

    if not payload.get("jti"):
        raise ValueError("token 缺少唯一标识")

    return payload


def _create_token(
    *,
    token_type: TokenType,
    user_id: str,
    expires_at: datetime,
    role: str | None,
    settings: Settings,
    token_jti: str | None = None,
) -> str:
    if not user_id:
        raise ValueError("用户标识不能为空")

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": token_type,
        # jti 后续会和 refresh_token 表关联，用于撤销、轮换和排查问题。
        "jti": token_jti or uuid4().hex,
        "iat": now,
        "exp": expires_at,
    }

    if role:
        payload["role"] = role

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
