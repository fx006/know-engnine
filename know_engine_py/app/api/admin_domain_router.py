from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.db.session import get_db
from know_engine_py.app.schemas.domain import DomainResponse
from know_engine_py.app.services.domain_config_service import DomainConfigService

router = APIRouter(prefix="/admin/domains",tags=["admin-domains"])

@router.get("",response_model=list[DomainResponse])
async def list_domains(db:AsyncSession=Depends(get_db)):
    """查询全部领域配置。"""
    service = DomainConfigService(db)
    return await service.list_domains()

@router.get("/{domain_id}",response_model=DomainResponse)
async def get_domain(domain_id:str,db:AsyncSession=Depends(get_db)):
    """查询单个领域配置，不存在时返回404。"""
    service = DomainConfigService(db)
    domain=await service.get_domain_by_id(domain_id)
    if domain is None:
        raise HTTPException(status_code=404,detail="领域不存在")
    return domain