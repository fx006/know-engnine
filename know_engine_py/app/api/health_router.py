from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Query
from sqlalchemy import text

from know_engine_py.app.core.settings import get_settings
from know_engine_py.app.db.session import get_session_maker

router = APIRouter()

HEALTH_COMPONENT_TIMEOUT_SECONDS = 6.0


@router.get("/health")
async def health_check(
    deep: bool = Query(
        default=False,
        description="是否执行真实外部依赖连通性检查",
    ),
):
    """返回应用和外部依赖的分层健康状态。

    默认只做轻量配置检查，避免普通健康探针阻塞在外部网络。
    需要真实连通性时传 `deep=true`，用于部署 smoke 或人工排障。
    """
    settings = get_settings()
    database, redis, minio, elasticsearch = await asyncio.gather(
        _check_with_timeout("数据库", _check_database(deep=deep)),
        _check_with_timeout("Redis", _check_redis(settings.redis_url, deep=deep)),
        _check_with_timeout("MinIO", _check_minio(settings, deep=deep)),
        _check_with_timeout(
            "Elasticsearch",
            _check_elasticsearch(settings.elasticsearch_url, deep=deep),
        ),
    )
    components = {
        "app": _component("ok", "应用进程可响应"),
        "database": database,
        "redis": redis,
        "minio": minio,
        "elasticsearch": elasticsearch,
        "llm": _check_llm_config(settings),
    }

    return {
        "status": _overall_status(components),
        "app_name": settings.app_name,
        "environment": settings.environment,
        "llm_chat_model": settings.llm_chat_model,
        "embedding_model": settings.embedding_model,
        "deep": deep,
        "components": components,
    }


def _component(status: str, detail: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": status,
        "detail": detail,
    }
    data.update(extra)
    return data


async def _check_with_timeout(
    component_name: str,
    check: Any,
) -> dict[str, Any]:
    """限制单个外部组件健康检查耗时，避免坏依赖拖死整个 health API。"""
    try:
        return await asyncio.wait_for(
            check,
            timeout=HEALTH_COMPONENT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return _component(
            "error",
            f"{component_name} 连通性检查超时",
            error=f"超过 {HEALTH_COMPONENT_TIMEOUT_SECONDS:.0f} 秒未返回",
        )
    except Exception as exc:
        return _component(
            "error",
            f"{component_name} 连通性检查失败",
            error=str(exc),
        )


def _overall_status(components: dict[str, dict[str, Any]]) -> str:
    if any(component["status"] == "error" for component in components.values()):
        return "degraded"
    return "ok"


async def _check_database(*, deep: bool) -> dict[str, Any]:
    if not deep:
        return _component("configured", "数据库配置已加载，未执行连通性检查")

    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            await session.execute(text("select 1"))
        return _component("ok", "数据库连通性正常")
    except Exception as exc:
        return _component("error", "数据库连通性检查失败", error=str(exc))


async def _check_redis(redis_url: str, *, deep: bool) -> dict[str, Any]:
    if not redis_url.strip():
        return _component("skipped", "Redis 未配置")

    if not deep:
        return _component("configured", "Redis 已配置，未执行连通性检查")

    try:
        from redis.asyncio import from_url

        client = from_url(redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return _component("ok", "Redis 连通性正常")
    except Exception as exc:
        return _component("error", "Redis 连通性检查失败", error=str(exc))


async def _check_minio(settings: Any, *, deep: bool) -> dict[str, Any]:
    if not settings.minio_endpoint.strip():
        return _component("skipped", "MinIO 未配置")

    if not deep:
        return _component("configured", "MinIO 已配置，未执行连通性检查")

    try:
        from minio import Minio

        client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        exists = await asyncio.to_thread(client.bucket_exists, settings.minio_bucket)
        if not exists:
            return _component(
                "error",
                "MinIO bucket 不存在",
                bucket=settings.minio_bucket,
            )
        return _component("ok", "MinIO 连通性正常", bucket=settings.minio_bucket)
    except Exception as exc:
        return _component("error", "MinIO 连通性检查失败", error=str(exc))


async def _check_elasticsearch(
    elasticsearch_url: str,
    *,
    deep: bool,
) -> dict[str, Any]:
    if not elasticsearch_url.strip():
        return _component("skipped", "Elasticsearch 未配置")

    if not deep:
        return _component("configured", "Elasticsearch 已配置，未执行连通性检查")

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(elasticsearch_url.rstrip("/"))
            response.raise_for_status()
        return _component("ok", "Elasticsearch 连通性正常")
    except Exception as exc:
        return _component("error", "Elasticsearch 连通性检查失败", error=str(exc))


def _check_llm_config(settings: Any) -> dict[str, Any]:
    if not settings.dashscope_api_key.strip():
        return _component("skipped", "DashScope API key 未配置")

    if not settings.dashscope_base_url.strip():
        return _component("error", "DashScope base URL 未配置")

    return _component("configured", "LLM 配置已加载，未执行模型调用")
