from pydantic import BaseModel,ConfigDict

class IntentResponse(BaseModel):

    """Admin 意图配置响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    domain_id:str
    intent_name:str
    intent_description:str|None=None
    retrieval_strategy:str
    data_sources:str
    sort_order:int
    is_active:int
