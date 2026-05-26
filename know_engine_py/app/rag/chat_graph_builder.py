from __future__ import annotations
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession


from know_engine_py.app.core.settings import Settings
from know_engine_py.app.domains.automotive.precondition_resolvers import (
    AutomotivePreconditionResolverRegistry,
)
from know_engine_py.app.rag.graph import build_rag_graph
from know_engine_py.app.rag.llms.factory import ChatModelFactory
from know_engine_py.app.rag.nodes.clarify_node import (
    PreconditionResolverRegistry,
    create_clarify_node,
)
from know_engine_py.app.rag.nodes.common_chat_node import create_common_chat_node
from know_engine_py.app.rag.nodes.generator_node import create_generator_node
from know_engine_py.app.rag.nodes.grader_node import create_grader_node
from know_engine_py.app.rag.nodes.intent_node import create_intent_node
from know_engine_py.app.rag.nodes.reference_node import create_reference_node
from know_engine_py.app.rag.nodes.reranker_node import create_reranker_node
from know_engine_py.app.rag.nodes.retrieve_node import DocumentRetrieverProviderProtocol
from know_engine_py.app.rag.nodes.route_executor_node import create_route_executor_node
from know_engine_py.app.rag.nodes.rewrite_node import create_rewrite_node
from know_engine_py.app.rag.nodes.router_node import create_router_node
from know_engine_py.app.rag.nodes.transform_node import create_transform_node
from know_engine_py.app.rag.rerankers.base import DocumentReranker
from know_engine_py.app.rag.rerankers.metadata_score import MetadataScoreReranker
from know_engine_py.app.rag.retrievers.document_retriever_provider import (
    DocumentRetrieverProvider,
)
from know_engine_py.app.services.domain_config_service import DomainConfigService
from know_engine_py.app.services.prompt_service import PromptService
from know_engine_py.app.rag.retrievers.text_to_sql_provider import TextToSqlRetrieverProvider


def build_chat_rag_graph(
    *,
    domain_config_service: DomainConfigService,
    prompt_service: PromptService,
    resolver_registry: PreconditionResolverRegistry,
    text_to_sql_retriever_provider: Any | None = None,
    document_retriever_provider: DocumentRetrieverProviderProtocol,
    fast_chat_model,
    chat_model,
    reranker: DocumentReranker | None = None,
):
    """组装聊天问答使用的 LangGraph。

    graph.py 只负责拓扑；
    chat_graph_builder.py 负责把数据库服务、模型、检索器提供者和各个 node 装配起来。

    这里注入的是 DocumentRetrieverProvider，而不是固定 retriever。
    原因是 router_node 会在运行时产出 route_strategy，
    route_executor_node 根据 route_plan 分发到文档检索和 Text-to-SQL。
    """
    document_reranker = reranker or MetadataScoreReranker()

    return build_rag_graph(
        intent_node=create_intent_node(prompt_service, fast_chat_model),
        clarify_node=create_clarify_node(
            domain_config_service,
            resolver_registry,
        ),
        common_chat_node=create_common_chat_node(prompt_service, chat_model),
        transform_node=create_transform_node(prompt_service, fast_chat_model),
        router_node=create_router_node(domain_config_service),
        route_executor_node=create_route_executor_node(
            document_retriever_provider=document_retriever_provider,
            text_to_sql_retriever_provider=text_to_sql_retriever_provider,
        ),
        reranker_node=create_reranker_node(document_reranker),
        grader_node=create_grader_node(prompt_service, fast_chat_model),
        rewrite_node=create_rewrite_node(prompt_service, fast_chat_model),
        reference_node=create_reference_node(),
        generator_node=create_generator_node(prompt_service, chat_model),
    )


def build_chat_rag_graph_from_db(
    *,
    db: AsyncSession,
    settings: Settings | None = None,
    reranker: DocumentReranker | None = None,
    document_retriever_provider: DocumentRetrieverProviderProtocol | None = None,
):
    """基于数据库 session 组装聊天图。

    这是 Chat API 接真实 LangGraph 的默认入口：
    - DomainConfigService / PromptService 依赖当前 DB session；
    - AutomotivePreconditionResolverRegistry 负责汽车领域澄清前置条件；
    - ChatModelFactory 负责创建快模型和生成模型；
    - DocumentRetrieverProvider 负责按 route_strategy 创建文档检索器。
    """
    domain_config_service = DomainConfigService(db)
    prompt_service = PromptService(db, domain_config_service)
    resolver_registry = AutomotivePreconditionResolverRegistry(db)

    model_factory = ChatModelFactory(settings=settings)
    fast_chat_model = model_factory.create_fast_chat_model()
    chat_model = model_factory.create_chat_model()

    provider = document_retriever_provider or DocumentRetrieverProvider(
        settings=settings,
    )

    text_to_sql_provider = TextToSqlRetrieverProvider(
        db=db,
        chat_model=chat_model,
        settings=settings,
        document_retriever_provider=provider,
    )

    return build_chat_rag_graph(
        domain_config_service=domain_config_service,
        prompt_service=prompt_service,
        resolver_registry=resolver_registry,
        document_retriever_provider=provider,
        text_to_sql_retriever_provider=text_to_sql_provider,
        fast_chat_model=fast_chat_model,
        chat_model=chat_model,
        reranker=reranker,
    )
