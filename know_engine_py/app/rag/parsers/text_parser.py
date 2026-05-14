from pathlib import Path
from know_engine_py.app.rag.parsers.base import BaseParser, ProcessedDocument, decode_utf8

class TextParser(BaseParser):
    """txt 文本解析器。"""

    def supports(self, file_name: str) -> bool:
        suffix = Path(file_name).suffix.lower()
        return suffix == ".txt"

    def parse(self, content: bytes, file_name: str) -> ProcessedDocument:
        text = decode_utf8(content, file_name)
        return ProcessedDocument(
            text=text,
            source_file_name=file_name,
            content_type="text/plain"
        )
