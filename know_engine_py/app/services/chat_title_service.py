from __future__ import annotations


class ChatTitleService:
    """聊天会话标题服务。

    当前阶段只负责确定性的标题兜底和归一化；后续可在这里接入
    快速模型生成标题，并在失败时降级为临时标题。
    """

    DEFAULT_TITLE = "新对话"
    TEMP_TITLE_MAX_LENGTH = 20

    def build_temporary_title(self, first_message: str | None) -> str:
        """根据用户首句生成临时标题。

        对齐 Java ChatController 的临时标题策略：先取用户问题前 20 个字符，
        后续再由异步 LLM 标题生成逻辑覆盖。
        """
        content = (first_message or "").strip()
        if not content:
            return self.DEFAULT_TITLE
        return content[: self.TEMP_TITLE_MAX_LENGTH]

    def normalize_title(self, title: str | None) -> str:
        """归一化标题，避免空标题落库。"""
        normalized = (title or "").strip()
        return normalized or self.DEFAULT_TITLE