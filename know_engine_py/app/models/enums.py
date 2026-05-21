from enum import Enum


class DocumentStatus(str, Enum):
    """文档生命周期状态，对齐 Java 版 DocumentStatus。"""

    INIT = "INIT"
    UPLOADED = "UPLOADED"
    CONVERTING = "CONVERTING"
    CONVERTED = "CONVERTED"
    CHUNKED = "CHUNKED"
    VECTOR_STORED = "VECTOR_STORED"
    STORED = "STORED"


class SegmentStatus(str, Enum):
    """文档切片状态，对齐 Java 版 SegmentStatus。"""

    STORED = "STORED"
    VECTOR_STORED = "VECTOR_STORED"


class KnowledgeBaseType(str, Enum):
    """知识库类型，对齐 Java 版 KnowledgeBaseType。"""

    DOCUMENT_SEARCH = "DOCUMENT_SEARCH"
    DATA_QUERY = "DATA_QUERY"

class ChatConversationStatus(str,Enum):
    """聊天会话状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class ChatMessageType(str, Enum):
    """聊天消息类型。"""
    USER = "USER"
    ASSISTANT = "ASSISTANT"