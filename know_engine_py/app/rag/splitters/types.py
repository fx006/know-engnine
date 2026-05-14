from dataclasses import dataclass
from enum import Enum


class SplitType(str, Enum):
    """文档切分策略类型"""

    LENGTH = "LENGTH"
    TITLE = "TITLE"
    REGEX = "REGEX"
    SMART = "SMART"
    SEPARATOR = "SEPARATOR"


@dataclass(slots=True)
class DocumentSplitParam:
    """一次文档切分的参数契约。
    这个对象属于 splitter 层内部契约，后续 API 请求体会转换成它。
    """

    split_type: SplitType = SplitType.TITLE
    chunk_size: int = 800
    overlap: int = 80
    title_level: int = 1
    regex: str | None = None
    separator: str | None = None

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")

        if self.overlap < 0 or self.overlap >= self.chunk_size:
            raise ValueError("overlap 必须大于0，并且小于chunk_size")

        if self.title_level <= 0:
            raise ValueError("title_level 必须大于0")

        if self.split_type == SplitType.REGEX and not self.regex:
            raise ValueError("使用 REGEX 切分时，必须提供正则表达式 regex")

        if self.split_type == SplitType.SEPARATOR and not self.separator:
            raise ValueError("使用 SEPARATOR 切分时，必须提供分隔符 separator")
