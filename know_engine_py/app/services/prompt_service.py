from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.config import PromptTemplateModel
from know_engine_py.app.services.domain_config_service import DomainConfigService

from sqlalchemy import select


class PromptService:
    """Prompt 模板服务。

    负责从数据库读取指定领域、意图、类型下的 Prompt 模板，
    并在指定意图缺少 Prompt 时回退到领域配置的 fallback 意图。
    """

    def __init__(
        self,
        db:AsyncSession,
        domain_config_service:DomainConfigService,):
        self.db=db
        self.domain_config_service=domain_config_service

    async def get_prompt(
            self,
            domain_id: str,
            intent_name: str,
            prompt_type: str,
    ) -> str | None:
        """查询指定意图的 Prompt；不存在时回退到 fallback 意图。

        查询时只取启用模板，并按 version 倒序取最新版本。
        如果 fallback 自己也没有 Prompt，则返回 None，避免无限递归。
        """
        prompt = await self._get_active_prompt_template(
            domain_id=domain_id,
            intent_name=intent_name,
            prompt_type=prompt_type,
        )

        if prompt is not None:
            return prompt.content

        domain = await self.domain_config_service.get_active_domain()

        # fallback 意图也查不到时直接返回 None，避免递归卡住。
        if intent_name == domain.fallback_intent:
            return None

        return await self.get_prompt(
            domain_id=domain_id,
            intent_name=domain.fallback_intent,
            prompt_type=prompt_type,
        )
    async def _get_active_prompt_template(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> PromptTemplateModel | None:
        """查询指定条件下最新的启用 Prompt 模板。"""
        result = await self.db.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.domain_id == domain_id)
            .where(PromptTemplateModel.intent_name == intent_name)
            .where(PromptTemplateModel.prompt_type == prompt_type)
            .where(PromptTemplateModel.is_active == 1)
            .order_by(PromptTemplateModel.version.desc())
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def build_intent_recognition_prompt(self)->str:
        """构建意图识别 Prompt。

        兼容两种模式：
        1. 完整 Prompt：没有占位符时直接返回，避免重复追加意图和实体。
        2. 通用模板 Prompt：包含占位符时，用数据库里的领域、意图和实体配置渲染。
        """
        domain= await self.domain_config_service.get_active_domain()
        intents = await self.domain_config_service.list_active_intents(domain.domain_id)

        base_prompt = await self.get_prompt(
            domain_id = domain.domain_id,
            intent_name="_system_",
            prompt_type="intent_recognition",
        )

        if not base_prompt:
            base_prompt = (
                "你是一个意图识别助手。\n\n"
                "{{intent_taxonomy}}\n\n"
                "{{entity_schema}}"
            )

        placeholders = {
            "{{domain_name}}": domain.name,
            "{{domain_description}}": domain.description or "",
            "{{intent_taxonomy}}": self._render_intent_taxonomy(intents),
            "{{entity_schema}}": self._render_entity_schema(domain.entity_schema),
        }

        # Java 原版 prompt 已经包含完整意图和实体说明；无占位符时原样返回。
        prompt = base_prompt
        for placeholder, value in placeholders.items():
            prompt = prompt.replace(placeholder, value)

        return prompt

    def _render_intent_taxonomy(self, intents) -> str:
        """将数据库中的意图配置渲染成 Prompt 片段。"""
        parts = ["## 意图类别"]
        for index,intent in enumerate(intents,start=1):
            parts.append(f"{index}. {intent.intent_name}")
            if intent.intent_description:
                parts.append(f"   - {intent.intent_description}")
        return "\n".join(parts)

    def _render_entity_schema(self, entity_schema: dict | None) -> str:
        """将领域实体配置渲染成 Prompt 片段。"""
        if not entity_schema:
            return ""

        parts = ["## 需要抽取的实体"]
        for field_name,description in entity_schema.items():
            parts.append(f"{field_name}: {description}")
        return "\n".join(parts)

    async def list_prompt_templates(
            self,
            domain_id:str,
            intent_name:str|None=None,
            prompt_type:str|None=None
    )->list[PromptTemplateModel]:
        """查询 Prompt 模板列表，供 Admin 管理端查看配置。"""
        stmt = select(PromptTemplateModel).where(
            PromptTemplateModel.domain_id==domain_id
        )

        if intent_name is not None:
            stmt = stmt.where(PromptTemplateModel.intent_name == intent_name)

        if prompt_type is not None:
            stmt = stmt.where(PromptTemplateModel.prompt_type == prompt_type)

        stmt = stmt.order_by(
            PromptTemplateModel.intent_name,
            PromptTemplateModel.prompt_type,
            PromptTemplateModel.version.desc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
