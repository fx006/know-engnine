from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx


class MinerUParseError(RuntimeError):
    """MinerU 文档解析失败。"""


@dataclass(slots=True)
class MinerUMarkdownResult:
    """MinerU 返回的 Markdown 解析结果。"""

    markdown: str
    source_file_name: str
    raw_response: dict[str, Any]


class MinerUClient:
    """MinerU 文件解析 HTTP 客户端。

    职责只限于调用外部 /file_parse 接口：
    - parse_to_markdown 返回 Markdown 文本。
    - parse_to_zip 返回 zip bytes。

    文档状态流转、MinIO 保存、segment 切分由上层 service/task 负责。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        timeout_seconds: float = 300.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    async def parse_to_markdown(
        self,
        *,
        file_name: str,
        content: bytes,
    ) -> MinerUMarkdownResult:
        """调用 MinerU，把 PDF/Word 等文件解析成 Markdown。"""
        response = await self._post_file_parse(
            file_name=file_name,
            content=content,
            response_format_zip=False,
            return_images=False,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MinerUParseError("MinerU 返回的不是合法 JSON") from exc

        markdown = self._extract_markdown(payload, file_name)
        return MinerUMarkdownResult(
            markdown=markdown,
            source_file_name=file_name,
            raw_response=payload,
        )

    async def parse_to_zip(
        self,
        *,
        file_name: str,
        content: bytes,
    ) -> bytes:
        """调用 MinerU，返回包含 Markdown 和图片的 zip bytes。"""
        response = await self._post_file_parse(
            file_name=file_name,
            content=content,
            response_format_zip=True,
            return_images=True,
        )
        return response.content

    async def _post_file_parse(
        self,
        *,
        file_name: str,
        content: bytes,
        response_format_zip: bool,
        return_images: bool,
    ) -> httpx.Response:
        if not self.base_url:
            raise MinerUParseError("MinerU 服务地址未配置")

        safe_file_name = Path(file_name).name or "document"
        url = f"{self.base_url}/file_parse"

        data = {
            "backend": "pipeline",
            "response_format_zip": self._bool_text(response_format_zip),
            "return_images": self._bool_text(return_images),
            "return_model_output": "false",
            "return_middle_json": "false",
        }
        files = {
            "files": (
                safe_file_name,
                content,
                "application/octet-stream",
            )
        }

        async with self._client() as client:
            response = await client.post(
                url,
                data=data,
                files=files,
                headers=self._headers(),
            )

        if response.status_code != 200:
            raise MinerUParseError(
                f"MinerU 解析失败：HTTP {response.status_code}，{response.text[:500]}"
            )

        return response

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self.http_client is not None:
            yield self.http_client
            return

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            yield client

    def _extract_markdown(self, payload: dict[str, Any], file_name: str) -> str:
        results = payload.get("results")
        if not isinstance(results, dict) or not results:
            raise MinerUParseError("MinerU 响应缺少 results")

        file_result = results.get(file_name)
        if file_result is None and len(results) == 1:
            file_result = next(iter(results.values()))

        if not isinstance(file_result, dict):
            raise MinerUParseError(f"MinerU 响应中找不到文件结果：{file_name}")

        markdown = file_result.get("md_content")
        if not isinstance(markdown, str):
            raise MinerUParseError("MinerU 响应缺少 md_content")

        return markdown

    def _bool_text(self, value: bool) -> str:
        return "true" if value else "false"