from pathlib import Path

from know_engine_py.app.rag.parsers.base import BaseParser, ProcessedDocument, decode_utf8

class MarkdownParser(BaseParser):
    """Markdown 文件解析器。"""

    def supports(self, file_name: str) -> bool:
        suffix = Path(file_name).suffix.lower()
        return suffix in {".md", ".markdown"}

    def parse(self, content: bytes, file_name: str) -> ProcessedDocument:
        text = decode_utf8(content, file_name)
        return ProcessedDocument(
            text=text,
            source_file_name=file_name,
            content_type="text/markdown"
        )
