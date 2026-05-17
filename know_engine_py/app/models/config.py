from sqlalchemy import JSON, Integer, SmallInteger, String, Text, UniqueConstraint, BigInteger
from sqlalchemy.orm import mapped_column,Mapped

from know_engine_py.app.models.base import Base,BaseEntity


class DomainConfigModel(Base,BaseEntity):
    __tablename__ = "domain_config"

    id: Mapped[int] =mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[str] = mapped_column(String(64),nullable=False,unique=True)
    name: Mapped[str] = mapped_column(String(128),nullable=False)
    description: Mapped[str | None] = mapped_column(String(512),nullable=True)
    entity_schema: Mapped[dict | None] = mapped_column(JSON,nullable=True)
    fallback_intent: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="其他",
        server_default="其他",
    )
    is_active: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1"
    )



class IntentConfigModel(Base, BaseEntity):
    __tablename__ = "intent_config"
    __table_args__ = (
        UniqueConstraint("domain_id", "intent_name", name="uk_domain_intent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    intent_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    retrieval_strategy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="hybrid",
        server_default="hybrid",
    )
    data_sources: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default='["milvus","es"]',
        server_default='["milvus","es"]',
    )
    # 决定进入RAG前是否要补充业务实体
    preconditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_active: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
    )




class PromptTemplateModel(Base, BaseEntity):
    __tablename__ = "prompt_template"
    __table_args__ = (
        UniqueConstraint(
            "domain_id",
            "intent_name",
            "prompt_type",
            "version",
            name="uk_prompt_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    domain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    is_active: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
    )
