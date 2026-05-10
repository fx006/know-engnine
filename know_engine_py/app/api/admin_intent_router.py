from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.db.session import get_db
from know_engine_py.app.schemas.intent import IntentResponse
from know_engine_py.app.services.domain_config_service import DomainConfigService

router=APIRouter(
    prefix="/admin/domains/{domain_id}/intents",
    tags=["admin-intents"],
)

@router.get("",response_model=list[IntentResponse])
async def list_intents_by_domain(
        domain_id:str,
        session:AsyncSession=Depends(get_db)
):
    """查询指定领域下的意图配置列表。"""
    service=DomainConfigService(session)
    intents=await service.list_intents_by_domain(domain_id)
    return intents
