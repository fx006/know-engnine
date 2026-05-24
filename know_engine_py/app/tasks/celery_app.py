from __future__ import annotations

from celery import Celery

from know_engine_py.app.core.settings import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """创建 Celery 应用实例。

    生产环境应显式配置 CELERY_BROKER_URL / CELERY_RESULT_BACKEND。
    本地未配置时降级到 memory broker，只用于导入、单测和学习阶段。
    """
    current_settings = settings or get_settings()

    broker_url = _resolve_broker_url(current_settings)
    result_backend = _resolve_result_backend(current_settings)

    app = Celery(
        "know_engine_py",
        broker=broker_url,
        backend=result_backend,
        include=["know_engine_py.app.tasks.document_tasks"],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        result_accept_content=["json"],
        timezone="Asia/Shanghai",
        enable_utc=False,
        task_track_started=True,
        task_ignore_result=False,
        broker_connection_retry_on_startup=True,
    )

    return app


def _resolve_broker_url(settings: Settings) -> str:
    """解析 broker 地址；Celery 专用配置优先，其次复用 Redis。"""
    if settings.celery_broker_url.strip():
        return settings.celery_broker_url

    if settings.redis_url.strip():
        return settings.redis_url

    return "memory://"


def _resolve_result_backend(settings: Settings) -> str | None:
    """解析结果后端；未配置时不启用结果持久化。"""
    if settings.celery_result_backend.strip():
        return settings.celery_result_backend

    if settings.redis_url.strip():
        return settings.redis_url

    return None


celery_app = create_celery_app()