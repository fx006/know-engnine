from pydantic import BaseModel,ConfigDict

class DomainResponse(BaseModel):
    """Admin 领域配置响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    domain_id: str
    name : str
    description : str | None = None
    entity_schema : dict |None = None
    fallback_intent: str
    is_active: int
