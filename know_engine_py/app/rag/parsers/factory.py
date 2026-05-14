from know_engine_py.app.rag.parsers.base import BaseParser, UnsupportedFileTypeError
from know_engine_py.app.rag.parsers.text_parser import TextParser
from know_engine_py.app.rag.parsers.markdown_parser import MarkdownParser

class ParserFactory:
    """文件解析工厂，根据文件名选择合适的解析器。"""

    def __init__(self, parsers: list[BaseParser] | None = None):
        self.parsers = parsers or [
            TextParser(),
            MarkdownParser(),
        ]

    def get_parser(self, file_name: str) -> BaseParser:
        """根据文件名选择 parser；找不到时抛出明确异常。"""
        for parser in self.parsers:
            if parser.supports(file_name):
                return parser
        raise UnsupportedFileTypeError(f"暂不支持的文件类型：{file_name}")
