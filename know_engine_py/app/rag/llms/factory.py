from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from know_engine_py.app.core.settings import Settings, get_settings


class ChatModelFactory:
    """创建项目统一使用的 LangChain ChatModel。

    当前通过 DashScope OpenAI-compatible endpoint 创建 `ChatOpenAI`。
    这里不直接发起对话请求，只负责模型对象创建，避免 LangGraph node
    各自散落模型名、base_url 和 api_key。
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def create_chat_model(self) -> BaseChatModel:
        """创建主生成模型，默认用于最终回答。"""
        return self._create(model=self.settings.llm_chat_model)

    def create_fast_chat_model(self) -> BaseChatModel:
        """创建快速模型，默认用于意图识别、查询改写等轻量节点。"""
        return self._create(model=self.settings.llm_fast_model)

    def _create(self, model: str) -> ChatOpenAI:
        self._validate_settings()
        return ChatOpenAI(
            model=model,
            api_key=self.settings.dashscope_api_key,
            base_url=self.settings.dashscope_base_url.rstrip("/"),
        )

    def _validate_settings(self) -> None:
        if not self.settings.dashscope_api_key.strip():
            raise ValueError("DASHSCOPE_API_KEY 不能为空")
