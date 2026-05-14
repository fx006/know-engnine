
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ProcessedDocument:
    """文件解析后的统一文本结果。"""
    text: str
    source_file_name: str
    content_type: str

class UnsupportedFileTypeError(ValueError):
    """文件类型暂不支持。"""


class BaseParser(ABC):
    """
    文件解析器基类。
    所有 *Parser 必须实现 supports() 和 process()
    """

    @abstractmethod
    def supports(self, file_name: str) -> bool:
        """判断当前解析器是否支持该文件。"""
        ...

    @abstractmethod
    def parse(self, content: bytes, file_name: str) -> ProcessedDocument:
        """把原始文件内容转为统一文本。"""
        ...

def decode_utf8(content: bytes, file_name: str) -> str:
    """按 UTF-8 解码文本类文件，失败时抛出输入内容非法异常。"""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"文件不是 UTF-8 文本：{file_name}") from exc
