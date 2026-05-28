from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.services.auth_service import AuthService

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """从 Authorization Bearer token 中解析当前用户。"""
    service = AuthService(db)

    try:
        return await service.get_current_user(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserModel | None:
    """可选解析当前用户。

    用于旧接口向登录态平滑过渡：未传 token 返回 None；传了 token 但无效则返回 401。
    """
    if credentials is None:
        return None

    service = AuthService(db)

    try:
        return await service.get_current_user(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def require_admin(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    """要求当前用户具备 admin 角色。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    return current_user
