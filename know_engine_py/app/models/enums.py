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


class GroupRole(str, Enum):
    """群组角色。"""

    SYSTEM_ADMIN = "system_admin"
    GROUP_OWNER = "group_owner"
    GROUP_MEMBER = "group_member"


class KnowledgeBaseVisibility(str, Enum):
    """知识库可见性。"""

    PRIVATE = "private"
    GROUP = "group"


class FileObjectStatus(str, Enum):
    """文件对象状态。"""

    ACTIVE = "active"


class UploadSessionStatus(str, Enum):
    """分片上传会话状态。"""

    UPLOADING = "uploading"
    COMPLETED = "completed"
    CANCELED = "canceled"


class UploadChunkStatus(str, Enum):
    """分片上传块状态。"""

    UPLOADED = "uploaded"


class DocumentTaskType(str, Enum):
    """文档 ETL 任务类型。"""

    CONVERT = "convert"
    SPLIT = "split"
    INDEX = "index"


class DocumentTaskStatus(str, Enum):
    """文档 ETL 任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELED = "canceled"
