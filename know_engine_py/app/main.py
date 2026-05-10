
from fastapi import FastAPI

from know_engine_py.app.api.health_router import router as health_router
from know_engine_py.app.api.admin_domain_router import router as admin_domain_router
from know_engine_py.app.api.admin_intent_router import router as admin_intent_router
from know_engine_py.app.api.admin_prompt_router import router as admin_prompt_router

app = FastAPI(title="know-engine-py")
app.include_router(health_router)
app.include_router(admin_domain_router)
app.include_router(admin_intent_router)
app.include_router(admin_prompt_router)