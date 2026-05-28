from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.dependencies.auth import get_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.schemas.auth import (
    AuthTokenResponse,
    AuthUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SuccessResponse,
)
from know_engine_py.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthUserResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """注册用户账号。"""
    service = AuthService(db)

    try:
        user = await service.register(
            username=request.username,
            password=request.password,
            nickname=request.nickname,
        )
        await db.commit()
        return user
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户名密码登录，返回 access token 和 refresh token。"""
    service = AuthService(db)

    try:
        token_pair = await service.login(
            username=request.username,
            password=request.password,
        )
        await db.commit()
        return token_pair
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用 refresh token 换取新的 token 对。"""
    service = AuthService(db)

    try:
        token_pair = await service.refresh(request.refresh_token)
        await db.commit()
        return token_pair
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """退出登录，撤销 refresh token。"""
    service = AuthService(db)

    try:
        await service.logout(request.refresh_token)
        await db.commit()
        return SuccessResponse(success=True)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=AuthUserResponse)
async def get_me(
    current_user: UserModel = Depends(get_current_user),
):
    """查询当前登录用户。"""
    return current_user
