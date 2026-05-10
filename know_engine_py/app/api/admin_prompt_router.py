from fastapi import APIRouter,Depends,Query
from sqlalchemy.ext.asyncio import AsyncSession
from know_engine_py.app.db.session import get_db

from know_engine_py.app.services.prompt_service import PromptService
from know_engine_py.app.services.domain_config_service import DomainConfigService
from know_engine_py.app.schemas.prompt import PromptTemplateResponse

router = APIRouter(prefix="/admin/domains/{domain_id}/prompts",tags=["admin-prompts"])

@router.get("",response_model=list[PromptTemplateResponse])
async def list_prompt_templates(
        domain_id:str,
        intent_name:str|None=Query(default=None),
        prompt_type:str|None=Query(default=None),
        db:AsyncSession=Depends(get_db),
):
    """查询指定领域下的 Prompt 模板列表。"""
    domain_config_service = DomainConfigService(db)
    prompt_service = PromptService(db,domain_config_service)

    return await prompt_service.list_prompt_templates(
        domain_id=domain_id,
        intent_name=intent_name,
        prompt_type=prompt_type
    )
