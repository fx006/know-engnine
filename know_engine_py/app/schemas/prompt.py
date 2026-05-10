from pydantic import BaseModel,ConfigDict

class PromptTemplateResponse(BaseModel):
    """Admin Prompt 模板响应模型。"""
    model_config = ConfigDict(from_attributes=True)

    domain_id:str
    intent_name:str
    prompt_type:str
    content:str
    version:int
    is_active:int
