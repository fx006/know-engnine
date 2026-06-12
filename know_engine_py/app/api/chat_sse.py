from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any


def sse_data(payload: str) -> str:
    """把业务 payload 包装成 text/event-stream 的 data 帧。"""
    lines = payload.splitlines() or [""]
    return "".join(f"data: {line}\n" for line in lines) + "\n"


def token_event(content: str) -> str:
    """输出普通回答内容。

    对齐 Java：LLM token 本身不加 [ANSWER] 前缀，直接作为流内容返回。
    """
    return sse_data(content)


def answer_delta_event(content: str) -> str:
    """输出答案增量。

    当前 wire format 仍保持 Java 兼容：答案文本不加业务前缀，直接写入 data。
    单独提供该函数，是为了让 API 层和后续前端都能用 answer_delta 语义命名。
    """
    return token_event(content)


def progress_event(message: str) -> str:
    """输出进度事件。"""
    return sse_data(f"[PROGRESS]:{message}")


def reference_event(references: list[dict[str, Any]]) -> str:
    """输出 RAG 引用事件。"""
    return sse_data(f"[REFERENCE]:{_to_json(references)}")


def done_event(conversation_id: str) -> str:
    """输出对话完成事件。"""
    return sse_data(f"[DONE]:{conversation_id}")


def warning_event(message: str) -> str:
    """输出警告事件。"""
    return sse_data(f"[WARN]:{message}")


def error_event(code: str, message: str) -> str:
    """输出错误事件。"""
    return sse_data(
        f"[ERROR]:{_to_json({'code': code, 'message': message})}"
    )


def clarification_events(events: Iterable[Mapping[str, Any]]) -> list[str]:
    """把 clarify_node 的内部事件映射成前端 SSE 事件。"""
    frames: list[str] = []

    for event in events:
        event_type = str(event.get("type") or "").strip()
        if not event_type:
            continue

        if event_type == "CARD":
            frames.append(sse_data(f"[CARD]:{event.get('message') or ''}"))
            continue

        if event_type == "WARN":
            frames.append(warning_event(str(event.get("message") or "")))
            continue

        if event_type.startswith("CARD_CHOICE"):
            items = event.get("items") or event.get("data") or []
            frames.append(sse_data(f"[{event_type}]:{_to_json(items)}"))
            continue

        raise ValueError(f"不支持的澄清事件类型：{event_type}")

    return frames


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
