from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.config import DomainConfigModel,IntentConfigModel

from sqlalchemy import select

class DomainConfigService:
    """领域配置服务。

    负责从数据库读取当前启用领域、领域下启用意图，
    并提供意图 fallback 能力，替代 Java 版硬编码 enum/switch。
    """
    def __init__(self,db: AsyncSession):
        self.db=db

    async def get_active_domain(self) -> DomainConfigModel:
        """查询当前启用的领域配置。"""
        result = await self.db.execute(
            select(DomainConfigModel)
            .where(DomainConfigModel.is_active==1)
        )
        return result.scalar_one()

    async def list_active_intents(self,domain_id:str)->list[IntentConfigModel]:
        """按 sort_order 查询指定领域下的启用意图列表。"""
        result = await self.db.execute(
            select(IntentConfigModel)
            .where(IntentConfigModel.domain_id==domain_id)
            .where(IntentConfigModel.is_active==1)
            .order_by(IntentConfigModel.sort_order)
        )
        return list(result.scalars().all())

    async def get_intent_or_fallback(
            self,
            domain_id:str,
            intent_name:str,)->IntentConfigModel|None:
        """查询指定意图；如果不存在，则返回当前领域的 fallback 意图。"""
        domain = await self.get_active_domain()
        intents = await self.list_active_intents(domain_id)
        for intent in intents:
            if intent.intent_name==intent_name:
                return intent
        for it in intents:
            if it.intent_name==domain.fallback_intent:
                return it
        return None

    async def list_domains(self)->list[DomainConfigModel]:
        """查询全部领域配置，供Admin管理端展示。"""
        result =await self.db.execute(
            select(DomainConfigModel)
            .order_by(DomainConfigModel.domain_id)
        )
        return list(result.scalars().all())

    async def get_domain_by_id(self,domain_id:str)->DomainConfigModel|None:
        """按domain_id查询领域详情；不存在时返回None。"""
        result = await self.db.execute(
            select(DomainConfigModel)
            .where(DomainConfigModel.domain_id==domain_id)
        )
        return result.scalar_one_or_none()

    async def list_intents_by_domain(self,domain_id:str)->list[IntentConfigModel]:
        """查询指定领域下的全部意图，按sort_order保持稳定顺序。"""
        result = await self.db.execute(
            select(IntentConfigModel)
            .where(IntentConfigModel.domain_id==domain_id)
            .order_by(IntentConfigModel.sort_order)
        )
        return list(result.scalars().all())