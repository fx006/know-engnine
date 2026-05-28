from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """注册请求体。"""

    username: str
    password: str
    nickname: str | None = None


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """刷新 access token 的请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(alias="refreshToken")


class LogoutRequest(BaseModel):
    """退出登录请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(alias="refreshToken")


class AuthUserResponse(BaseModel):
    """认证用户响应模型，不能暴露 password_hash。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user_id: str = Field(alias="userId")
    username: str
    nickname: str | None = None
    role: str
    status: str
    last_login_at: datetime | None = Field(default=None, alias="lastLoginAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AuthTokenResponse(BaseModel):
    """登录/刷新成功后的 token 响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(alias="tokenType")
    expires_in: int = Field(alias="expiresIn")
    user: AuthUserResponse


class SuccessResponse(BaseModel):
    """通用成功响应。"""

    success: bool
