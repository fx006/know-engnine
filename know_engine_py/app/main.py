
from fastapi import FastAPI

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

app = FastAPI(title="know-engine-py")
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
