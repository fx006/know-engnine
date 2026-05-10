from fastapi import APIRouter

from know_engine_py.app.core.settings import get_settings

router = APIRouter()


@router.get("/health")
def health_check():
    settings = get_settings()

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.environment,
        "llm_chat_model": settings.llm_chat_model,
        "embedding_model": settings.embedding_model,
    }
