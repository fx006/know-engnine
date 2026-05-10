# Know-Engine Python 10 天全量冲刺带学计划

> 生成日期：2026-05-04
>
> 目标读者：有 Java 后端经验、已学 Python 语法、希望通过真实 RAG 项目转向 Python 大模型应用开发的学习者。

## 1. 总目标

在 10 天内，以 Java 版 `know-engine` 为参考，完成一个 Python 版 RAG 应用工程。项目不按“玩具 demo”处理，而按真实后端项目组织：FastAPI 提供接口，SQLAlchemy 管理业务数据，LangGraph 编排 RAG 状态机，DashScope 提供大模型与 embedding，Milvus/Elasticsearch/Neo4j 提供多源检索，Redis/Celery/MinIO 支撑缓存、异步任务和文件存储。

本计划的核心不是“让 AI 一次性写完”，而是采用“带学式结对开发”：

- 你负责手敲关键代码，建立语法、框架和工程肌肉记忆。
- 我负责讲设计、拆任务、给骨架、审代码、解释报错、补测试思路。
- 每天都要留下可运行结果，避免只堆文件不闭环。
- 全量目标不缩水，但实现深度分层：先跑通，再加厚，再包装成面试项目。

## 2. 项目边界

### 2.1 必做能力

- FastAPI 应用启动、路由分层、依赖注入、生命周期管理。
- Pydantic Settings 配置管理，支持 DashScope、MySQL、Redis、Milvus、Elasticsearch、Neo4j、MinIO。
- SQLAlchemy 2.0 async ORM，迁移核心业务表和新增动态配置表。
- 动态领域配置：`domain_config`、`intent_config`、`prompt_template`。
- Prompt 动态拼装与缓存，替代 Java 版汽车领域硬编码。
- 文档上传、解析、切分、segment 入库。
- DashScope embedding，向量数据写入 Milvus。
- Elasticsearch 关键词检索，Milvus 向量检索，RRF 融合。
- BGE reranker 或可替换 reranker 封装。
- LangGraph RAG 状态机：意图识别、查询改写、路由、检索、重排、评分、重写、生成。
- Corrective RAG 循环：检索质量差时自动 rewrite 后重试。
- SSE 流式聊天接口，包含 `[PROGRESS]`、`[REFERENCE]`、`[DONE]` 协议。
- 会话和消息持久化，包含 transform content、RAG references。
- Celery 异步任务和简版补偿任务。
- Docker Compose 本地运行。
- README、架构图、接口说明、面试讲解材料。

### 2.2 深度分层

为了 10 天内保持可完成性，每个模块按三层推进：

- 第 1 层：接口和主链路跑通。
- 第 2 层：补状态、异常、缓存、测试、异步。
- 第 3 层：补面试表达、技术取舍、可扩展设计。

例如 MinerU、Neo4j、Celery 不直接砍掉，但允许先完成“可替换接口 + 最小可运行实现”，再逐步加厚。

## 3. 技术选型

### 3.1 后端框架

- Python：`>=3.10`
- Web：`FastAPI`
- 数据校验：`Pydantic v2`
- 配置：`pydantic-settings`
- ORM：`SQLAlchemy 2.0 async`
- 迁移：`Alembic`
- 测试：`pytest`、`pytest-asyncio`、`httpx`

### 3.2 大模型与 RAG

- LLM Provider：阿里云百炼 DashScope
- 推荐接入方式：OpenAI-compatible 协议
- 生成模型：`qwen-plus`
- 快速任务模型：`qwen-turbo` 或 `qwen-flash`
- Embedding：`text-embedding-v4`
- 编排：`LangGraph`
- LangChain：用于 message、document、retriever 等通用抽象

### 3.3 存储与检索

- MySQL：业务数据、配置数据、会话消息。
- Redis：配置缓存、Prompt 缓存、Celery broker。
- MinIO：原始文件存储。
- Milvus：向量检索。
- Elasticsearch：关键词检索和 chunk 原文索引。
- Neo4j：图谱检索，先做简版样例链路。

## 4. 我带你写的方式

### 4.1 每个任务的固定节奏

每个模块按下面 7 步推进：

1. 对照 Java 版：先说明 Java 里对应类、方法和职责。
2. Python 化设计：解释 Python/FastAPI/SQLAlchemy/LangGraph 里如何表达同一职责。
3. 给文件骨架：我只给结构、类型、关键 TODO，不一次性塞满实现。
4. 你手敲核心逻辑：尤其是 ORM、service、router、graph node。
5. 我 review：检查命名、异步写法、事务、异常、类型、测试。
6. 跑验证命令：当天必须有可运行结果。
7. 记录面试点：整理成 3-5 句话，方便最后写 README。

### 4.2 哪些代码必须你手敲

这些是学习收益最高的部分，不建议完全交给我生成：

- FastAPI router 和 dependency。
- Pydantic schema。
- SQLAlchemy model 和 query。
- Service 层业务逻辑。
- LangGraph `AgentState` 和各个 node。
- SSE streaming generator。
- 测试用例。

### 4.3 哪些代码我可以多给一点

这些偏机械或容易耗时间，可以由我给完整初稿，你再阅读和微调：

- Docker Compose。
- Alembic 初始配置。
- 枚举和常量平移。
- README 结构。
- 简单工具类。
- 种子 YAML。
- Makefile 或常用脚本。

### 4.4 每天如何协作

每天开始时，你可以直接发：

```text
开始 Day N，先带我做第一个任务。
```

我会按这个格式回应：

- 今天目标。
- 先讲 10 分钟概念。
- 第一个要创建或修改的文件。
- 你应该手敲的代码块。
- 跑什么命令验证。
- 如果报错，把报错贴回来，我按 Python 学习视角解释。

## 5. 目录规划

建议 Python 项目放在仓库根目录下的 `know_engine_py/`：

```text
know_engine_py/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── rag/
│   │   ├── nodes/
│   │   ├── retrievers/
│   │   └── graph.py
│   ├── tasks/
│   ├── utils/
│   └── main.py
├── config/
│   └── domains/
├── prompts/
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

如果后续你希望根目录直接就是 Python 项目，也可以把 `app/`、`tests/`、`pyproject.toml` 放在仓库根目录。考虑到当前仓库已有 `res/` 和 `doc/`，推荐先用 `know_engine_py/` 隔离。

## 6. 10 天计划

### Day 1：项目骨架与运行闭环

目标：创建 Python 项目骨架，跑起 FastAPI，完成配置读取和健康检查。

核心文件：

- `know_engine_py/pyproject.toml`
- `know_engine_py/app/main.py`
- `know_engine_py/app/core/settings.py`
- `know_engine_py/app/api/health_router.py`
- `know_engine_py/tests/test_health.py`

学习重点：

- Python 包结构和 `__init__.py`。
- FastAPI app、router、lifespan。
- Pydantic Settings。
- pytest + httpx 测接口。
- Java Spring Boot 配置到 FastAPI 配置的迁移思路。

验收标准：

- `uvicorn app.main:app --reload` 可以启动。
- `GET /health` 返回应用名称、环境、模型配置摘要。
- 测试能跑通。

当天面试点：

- 为什么使用 FastAPI 而不是 Flask。
- Python 配置如何替代 Spring `application.yml`。
- 如何隔离模型供应商配置。

### Day 2：数据库模型与动态配置表

目标：用 SQLAlchemy async 建立核心 ORM 模型，完成数据库连接和基础 CRUD。

核心文件：

- `know_engine_py/app/db/session.py`
- `know_engine_py/app/db/base.py`
- `know_engine_py/app/models/base.py`
- `know_engine_py/app/models/domain_config.py`
- `know_engine_py/app/models/intent_config.py`
- `know_engine_py/app/models/prompt_template.py`
- `know_engine_py/app/models/chat.py`
- `know_engine_py/app/models/document.py`
- `know_engine_py/app/schemas/config.py`

学习重点：

- SQLAlchemy 2.0 `Mapped`、`mapped_column`。
- async session 的生命周期。
- Java MyBatis-Plus entity 到 Python ORM 的映射。
- JSON 字段、唯一索引、时间字段。

验收标准：

- 能创建表。
- 能插入一个 domain、intent、prompt。
- 能查询并返回 Pydantic schema。

当天面试点：

- 为什么把领域、意图、Prompt DB 化。
- 如何消除 Java 版汽车领域硬编码。

### Day 3：配置服务、Prompt 服务和 Admin API

目标：实现动态领域配置服务、Prompt 动态拼装、配置管理接口。

核心文件：

- `know_engine_py/app/services/domain_config_service.py`
- `know_engine_py/app/services/prompt_service.py`
- `know_engine_py/app/api/admin_router.py`
- `know_engine_py/config/domains/automotive.yaml`
- `know_engine_py/prompts/automotive/*.txt`
- `know_engine_py/tests/test_prompt_service.py`

学习重点：

- Service 层组织方式。
- Redis 缓存读写和失效。
- Pydantic schema 与 ORM model 的边界。
- Prompt 模板如何从“文件硬编码”升级为“配置化”。

验收标准：

- 启动时可导入汽车领域种子数据。
- `GET /api/admin/intents` 返回汽车意图。
- 修改 Prompt 后缓存失效。
- `build_intent_recognition_prompt()` 自动拼出意图列表和实体字段。

当天面试点：

- 领域配置热更新。
- 新增意图不需要改代码。
- Prompt 管理如何支撑多领域扩展。

### Day 4：文档上传、解析入口和切分

目标：建立文档处理主流程，先跑通 Markdown/txt，预留 PDF/MinerU 接口。

核心文件：

- `know_engine_py/app/services/file_storage_service.py`
- `know_engine_py/app/services/file_process_service.py`
- `know_engine_py/app/services/document_splitter.py`
- `know_engine_py/app/services/document_process_service.py`
- `know_engine_py/app/api/document_router.py`
- `know_engine_py/app/models/document.py`
- `know_engine_py/tests/test_document_splitter.py`

学习重点：

- 文件上传接口。
- MinIO SDK 封装。
- 策略模式/工厂模式在 Python 里的写法。
- Java 文档处理 service 到 Python service 的平移。
- chunk metadata 设计。

验收标准：

- 上传或导入 Markdown/txt 后生成 document 记录。
- split 后生成 segment 记录。
- segment 包含 `docId`、`chunkId`、`parentChunkId`、`fileName` 等 metadata。

当天面试点：

- 为什么 chunk metadata 决定 RAG 可溯源能力。
- 为什么先抽象 MinerU 客户端而不是把解析逻辑写死。

### Day 5：Embedding、Milvus、Elasticsearch 和混合检索

目标：完成文档向量化、Milvus 写入、ES 索引、Hybrid Retriever。

核心文件：

- `know_engine_py/app/services/embedding_service.py`
- `know_engine_py/app/rag/retrievers/milvus_retriever.py`
- `know_engine_py/app/rag/retrievers/es_retriever.py`
- `know_engine_py/app/rag/retrievers/hybrid_retriever.py`
- `know_engine_py/app/rag/retrievers/rrf.py`
- `know_engine_py/tests/test_rrf.py`

学习重点：

- DashScope embedding 调用。
- LangChain `Document` 抽象。
- Milvus collection/schema/index。
- ES BM25 查询。
- RRF 融合算法。
- 并发检索：`asyncio.gather`。

验收标准：

- 文档 segment 可以写入 Milvus 和 ES。
- 输入 query 可以分别拿到向量检索、关键词检索、融合检索结果。
- RRF 有单元测试。

当天面试点：

- 为什么 ES 不再同时承担向量和全文检索。
- 为什么使用 RRF 做召回融合。

### Day 6：LangGraph 基础 RAG 状态机

目标：实现第一版可运行 LangGraph：intent、transform、router、retrieve、generate。

核心文件：

- `know_engine_py/app/rag/state.py`
- `know_engine_py/app/rag/nodes/intent_node.py`
- `know_engine_py/app/rag/nodes/transform_node.py`
- `know_engine_py/app/rag/nodes/router_node.py`
- `know_engine_py/app/rag/nodes/retriever_node.py`
- `know_engine_py/app/rag/nodes/generator_node.py`
- `know_engine_py/app/rag/graph.py`
- `know_engine_py/tests/test_graph_smoke.py`

学习重点：

- `TypedDict` 状态定义。
- LangGraph node 的输入输出。
- 条件边和普通边。
- DashScope chat model 封装。
- Java 线性管道到 LangGraph 状态机的升级。

验收标准：

- 输入汽车相关问题，走 RAG 分支。
- 输入闲聊问题，走 common chat 分支。
- graph smoke test 能返回最终 response。

当天面试点：

- LangGraph 相比普通 Chain 的价值。
- 状态机为什么适合 Corrective RAG。

### Day 7：Rerank、Grader、Rewrite 和 Corrective RAG

目标：补齐 RAG 质量控制链路，实现“不相关则重写重试”。

核心文件：

- `know_engine_py/app/rag/nodes/reranker_node.py`
- `know_engine_py/app/rag/nodes/grader_node.py`
- `know_engine_py/app/rag/nodes/rewrite_node.py`
- `know_engine_py/app/rag/nodes/prompt_select_node.py`
- `know_engine_py/app/rag/graph.py`
- `know_engine_py/tests/test_corrective_rag.py`

学习重点：

- reranker 封装。
- LLM grader 的 JSON/yes-no 输出约束。
- LangGraph 循环边。
- 最大重试次数控制。
- Prompt 动态选择。

验收标准：

- 检索为空或评分不合格时进入 rewrite。
- retry 达到上限后停止循环。
- 最终使用对应意图的 chat prompt 生成。

当天面试点：

- Java 版线性管道的局限。
- Corrective RAG 如何降低低质量上下文带来的幻觉。

### Day 8：聊天会话、消息持久化和 SSE

目标：实现最终用户对话接口，支持流式返回、进度事件、引用溯源、消息回写。

核心文件：

- `know_engine_py/app/services/chat_conversation_service.py`
- `know_engine_py/app/services/chat_message_service.py`
- `know_engine_py/app/services/title_summary_service.py`
- `know_engine_py/app/api/chat_router.py`
- `know_engine_py/tests/test_chat_api.py`

学习重点：

- FastAPI `StreamingResponse`。
- SSE 协议格式。
- async generator。
- 消息先创建、后回写的设计。
- 背景任务和标题生成。

验收标准：

- `POST /chat/send` 返回 SSE。
- 能看到 `[PROGRESS]`、`[REFERENCE]`、回答内容、`[DONE]`。
- DB 中保存 user message、assistant message、transform content、rag references。

当天面试点：

- SSE 为什么适合大模型流式输出。
- 如何保证回答内容和引用最终可追溯。

### Day 9：Celery、MinerU、Neo4j 和工程补强

目标：把异步任务、PDF 解析入口、图谱检索接入整体架构。

核心文件：

- `know_engine_py/app/tasks/celery_app.py`
- `know_engine_py/app/tasks/document_tasks.py`
- `know_engine_py/app/services/mineru_client.py`
- `know_engine_py/app/rag/retrievers/neo4j_retriever.py`
- `know_engine_py/app/rag/nodes/retriever_node.py`
- `know_engine_py/docker-compose.yml`

学习重点：

- Celery worker 和 broker。
- 文档处理异步化。
- 补偿任务的设计。
- Neo4j 查询封装。
- 外部服务失败时如何降级。

验收标准：

- 上传文档后可以异步处理。
- Celery worker 能执行文档切分和入库任务。
- Neo4j retriever 有最小可运行样例或清晰 fallback。

当天面试点：

- 为什么文档处理不能阻塞 HTTP 请求。
- 如何替代 Java 版 XXL-Job。
- 图谱检索适合解决什么问题。

### Day 10：测试、部署、README 和面试材料

目标：完成可演示版本，整理项目表达。

核心文件：

- `know_engine_py/README.md`
- `know_engine_py/docker-compose.yml`
- `know_engine_py/.env.example`
- `know_engine_py/tests/`
- `doc/interview_talking_points.md`

学习重点：

- 冒烟测试。
- 接口测试。
- Docker Compose 联调。
- README 的工程表达。
- 面试时如何讲架构、难点和取舍。

验收标准：

- 本地一键启动基础服务。
- 完成 3 条演示路径：
  - 领域配置 API。
  - 文档导入和检索。
  - SSE RAG 问答。
- README 包含架构图、运行方式、核心亮点。
- 面试话术文档完成。

当天面试点：

- 从 Java RAG 到 Python LangGraph 的架构升级。
- 多源检索、Prompt 配置化、Corrective RAG、SSE 流式输出。
- 哪些是当前已实现，哪些是后续可扩展。

## 7. 每天的学习检查清单

每天结束前回答这 5 个问题：

1. 今天我新学了哪 3 个 Python/框架概念？
2. 今天哪个模块对应 Java 项目里的哪个类？
3. 今天的代码入口在哪里？
4. 如果面试官问“为什么这么设计”，我怎么回答？
5. 明天最容易卡住的风险是什么？

## 8. 代码练习规则

为了达到“熟悉语法和框架”的目的，执行时遵守这些规则：

- 我不一次性生成整天代码，除非你明确要求。
- 每次只推进一个小模块。
- 核心代码优先你手敲，我负责解释和检查。
- 报错优先让你先读一遍 traceback，我再逐层解释。
- 每天至少写 2 个测试：一个单元测试，一个接口或集成测试。
- 每个 service 都要能说清楚输入、输出、副作用。
- 所有外部依赖都通过配置和封装隔离，不在业务代码里散落 API key 或 SDK 细节。

## 9. DashScope 接入约定

`.env` 建议配置：

```env
DASHSCOPE_API_KEY=your-api-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_CHAT_MODEL=qwen-plus
LLM_FAST_MODEL=qwen-turbo
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
```

封装目标：

- `LLMService.chat()`：用于普通生成。
- `LLMService.fast_chat()`：用于意图识别、改写、评分、标题。
- `EmbeddingService.embed_query()`：用于 query embedding。
- `EmbeddingService.embed_documents()`：用于 chunk embedding。

业务代码只依赖这些 service，不直接依赖 DashScope SDK。这样后续切换 DeepSeek、OpenAI、硅基流动或本地 Ollama 时，只需要替换 service 实现和配置。

## 10. 风险和应对

### 10.1 外部服务太多导致环境卡住

应对：

- 第一次实现时保留 fallback。
- Milvus/ES/Neo4j 任一服务未启动时，返回清晰错误。
- 文档处理先支持本地 Markdown/txt，再接 MinerU。

### 10.2 Python async 不熟导致事务或 session 出错

应对：

- 所有数据库操作先写小测试。
- 明确区分 router、service、repository/ORM 的职责。
- 不在全局保存 `AsyncSession`。

### 10.3 LangGraph 一次性写太复杂

应对：

- Day 6 只写无循环基础图。
- Day 7 再加 grader/rewrite 循环。
- 每个 node 单独测试，再测整图。

### 10.4 学习目标被赶工吞掉

应对：

- 你手敲核心逻辑。
- 每天写学习检查清单。
- 每天产出面试话术。
- 我解释“为什么”，不只给“怎么写”。

## 11. 最终交付物

10 天结束时，目标交付：

- 一个可运行的 `know_engine_py` Python 项目。
- 完整 README。
- Docker Compose。
- `.env.example`。
- 核心接口测试。
- RAG 主链路演示。
- 动态领域配置演示。
- SSE 聊天演示。
- `doc/interview_talking_points.md` 面试讲解文档。

最终面试表达可以收敛为：

> 我基于一个 Java RAG 项目做了 Python 架构升级。原项目使用线性 RAG 管道，并且汽车领域意图和 Prompt 存在硬编码。我用 FastAPI + SQLAlchemy 重建业务服务，用数据库配置化领域、意图和 Prompt，用 LangGraph 编排可循环的 Corrective RAG 状态机，并将检索拆分为 Milvus 向量检索、Elasticsearch 关键词检索和 Neo4j 图谱检索，最后通过 SSE 实现进度、引用和答案的流式返回。这个项目让我系统掌握了 Python 后端、大模型调用、RAG 工程化和异步任务处理。

