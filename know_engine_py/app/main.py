
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from know_engine_py.app.api.health_router import router as health_router
from know_engine_py.app.api.admin_domain_router import router as admin_domain_router
from know_engine_py.app.api.admin_intent_router import router as admin_intent_router
from know_engine_py.app.api.admin_prompt_router import router as admin_prompt_router
from know_engine_py.app.api.document_router import router as document_router
from know_engine_py.app.api.document_task_router import router as document_task_router
from know_engine_py.app.api.chat_router import router as chat_router
from know_engine_py.app.api.auth_router import router as auth_router
from know_engine_py.app.api.access_control_router import router as access_control_router
from know_engine_py.app.api.upload_router import router as upload_router
from know_engine_py.app.core.settings import get_settings

logger = logging.getLogger(__name__)

app = FastAPI(title="know-engine-py")
settings = get_settings()


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request | None,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """把数据库底层异常映射成稳定 JSON，避免浏览器收到不透明的 CORS 网络错误。"""
    logger.exception("数据库访问异常", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "数据库服务暂不可用，请稍后重试或检查数据库连接",
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(access_control_router)
app.include_router(upload_router)
app.include_router(admin_domain_router)
app.include_router(admin_intent_router)
app.include_router(admin_prompt_router)
app.include_router(document_router)
app.include_router(document_task_router)
app.include_router(chat_router)
