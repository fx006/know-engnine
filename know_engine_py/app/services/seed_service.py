from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models import DomainConfigModel, IntentConfigModel, PromptTemplateModel


class SeedService:
    """领域包初始化服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_domain_package(self,yaml_path:Path)->None:
        """导入一个领域包YAML,并写入领域/意图/Prompt 三类配置。"""
        package = self._load_yaml(yaml_path=yaml_path)
        domain_cfg = package["domain"]

        # 约定：automotive.yaml 对应目录 automotive/
        package_dir = yaml_path.parent / yaml_path.stem

        domain:DomainConfigModel = await self._upsert_domain(domain_cfg)

        intent_recognition_cfg = package.get("intent_recognition")
        if intent_recognition_cfg:
            content = self._read_prompt_content(
                package_dir=package_dir,
                yaml_dir = yaml_path.parent,
                content_file = intent_recognition_cfg["content_file"]
            )
            await self._upsert_prompt_template(
                domain_id=domain.domain_id,
                intent_name="_system_",
                prompt_type=intent_recognition_cfg.get("prompt_type","intent_recognition"),
                content=content,
                version=int(intent_recognition_cfg.get("version",1)),
                is_active=int(intent_recognition_cfg.get("is_active",1)),
            )
        for intent_cfg in package.get("intents",[]):
            intent:IntentConfigModel = await self._upsert_intent(domain.domain_id,intent_cfg)

            prompt_cfg=intent_cfg["prompt"]
            content = self._read_prompt_content(
                package_dir=package_dir,
                yaml_dir=yaml_path.parent,
                content_file=prompt_cfg["content_file"],
            )
            await self._upsert_prompt_template(
                domain_id=domain.domain_id,
                intent_name=intent.intent_name,
                prompt_type=prompt_cfg.get("prompt_type","chat"),
                content=content,
                version=int(prompt_cfg.get("version",1)),
                is_active=int(prompt_cfg.get("is_active",1))
            )
        await self.session.flush()

    async def _upsert_domain(self,cfg:dict[str,Any])->DomainConfigModel:
        """按 domain_id upsert领域配置"""
        result = await self.session.execute(
            select(DomainConfigModel).where(DomainConfigModel.domain_id==cfg["domain_id"])
        )
        domain=result.scalar_one_or_none()

        if domain is None:
            domain=DomainConfigModel(
                domain_id=cfg["domain_id"],
                name=cfg["name"],
            )
            self.session.add(domain)

        domain.name = cfg["name"]
        domain.description = cfg.get("description")
        domain.entity_schema = cfg.get("entity_schema")
        domain.fallback_intent = cfg.get("fallback_intent", "其他")
        domain.is_active = int(cfg.get("is_active", 1))
        return domain

    async def _upsert_intent(self, domain_id: str, cfg: dict[str, Any]) -> IntentConfigModel:
        """按 (domain_id, intent_name) upsert 意图配置。"""
        result = await self.session.execute(
            select(IntentConfigModel).where(
                IntentConfigModel.domain_id == domain_id,
                IntentConfigModel.intent_name == cfg["intent_name"],
            )
        )
        intent = result.scalar_one_or_none()

        if intent is None:
            intent = IntentConfigModel(
                domain_id=domain_id,
                intent_name=cfg["intent_name"],
            )
            self.session.add(intent)

        data_sources = cfg.get("data_sources", '["milvus","es"]')
        if isinstance(data_sources, list):
            data_sources = json.dumps(data_sources, ensure_ascii=False)

        intent.intent_description = cfg.get("intent_description")
        intent.retrieval_strategy = cfg.get("retrieval_strategy", "hybrid")
        intent.data_sources = data_sources
        intent.sort_order = int(cfg.get("sort_order", 0))
        intent.is_active = int(cfg.get("is_active", 1))
        return intent

    async def _upsert_prompt_template(
            self,
            domain_id: str,
            intent_name: str,
            prompt_type: str,
            content: str,
            version: int,
            is_active: int,
    ) -> PromptTemplateModel:
        """按唯一键 (domain, intent, type, version) upsert Prompt。"""
        result = await self.session.execute(
            select(PromptTemplateModel).where(
                PromptTemplateModel.domain_id == domain_id,
                PromptTemplateModel.intent_name == intent_name,
                PromptTemplateModel.prompt_type == prompt_type,
                PromptTemplateModel.version == version,
            )
        )
        prompt = result.scalar_one_or_none()

        if prompt is None:
            prompt = PromptTemplateModel(
                domain_id=domain_id,
                intent_name=intent_name,
                prompt_type=prompt_type,
                version=version,
                content=content,
                is_active=is_active,
            )
            self.session.add(prompt)
            return prompt

        prompt.content = content
        prompt.is_active = is_active
        return prompt

    def _load_yaml(self, yaml_path: Path) -> dict[str, Any]:
        """读取并解析 YAML。"""
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"YAML 内容非法：{yaml_path}")
        if "domain" not in data:
            raise ValueError(f"YAML缺少domain节点：{yaml_path}")
        return data

    def _read_prompt_content(self,package_dir: Path, yaml_dir: Path, content_file: str) -> str:
        """读取 prompt文本，优先从<yaml_stem>/ 下解析"""
        rel = Path(content_file)
        candidates = [package_dir / rel, yaml_dir / rel]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"找不到 prompt 文件：{content_file}")
