# AGENTS.md

## 交流习惯

- 非明确告知情况下，思考过程及回答尽量使用中文。
- 用户是 Java 后端开发者，已学习 Python 基础语法，当前目标是通过一个真实 RAG 项目熟悉 Python 大模型应用开发。
- 回复风格应偏“导师 + 结对编程”：先解释设计，再给骨架，再让用户手敲核心逻辑，最后 review 和验收。
- 不要默认一次性生成完整大段业务代码。用户的核心诉求是通过手敲或半手敲加强学习和记忆。

## 项目背景

当前工作目录：`/Users/fantasy/code/konw-engine`

已有参考项目：

- Java 原版 RAG 项目：`res/LLMentor/know-engine`
- 该项目来自一位阿里工作八年的博主，用户已付费购买，当前仍在更新且闭源。
- 用户希望以此为契机，将 Java RAG 项目改造为 Python 项目，作为转型大模型应用开发方向的练手项目和面试项目经历。

已有规划文档：

- 改造大纲：`doc/migration_plan_final.md`
- 详细实施蓝图上：`doc/implementation_blueprint.md`
- 详细实施蓝图下：`doc/implementation_blueprint_part2.md`
- 10 天全量冲刺带学计划：`doc/10_day_full_sprint_learning_plan.md`
- 进度跟踪文档：`doc/progress_tracker.md`
- 每日学习笔记目录：`doc/learning_notes/`

## 总体目标

在 10 天左右，以每天约 8 小时投入，完成 Python 版 Know-Engine RAG 应用工程。

目标不是缩水成简单 demo，而是在全量目标下分层交付：

1. 先跑通主链路。
2. 再加厚工程能力。
3. 最后整理成面试可讲项目。

最终项目表达：

> 基于 Java RAG 项目做 Python 架构升级：使用 FastAPI + SQLAlchemy 重建业务服务，用数据库配置化领域、意图和 Prompt，用 LangGraph 编排可循环 Corrective RAG 状态机，将检索拆分为 Milvus 向量检索、Elasticsearch 关键词检索和 Neo4j 图谱检索，并通过 SSE 实现进度、引用和答案的流式返回。

## 依据优先级与设计取舍

开发时参考依据按以下顺序理解，但允许基于工程判断做取舍：

1. Java 原项目 `res/LLMentor/know-engine` 是业务事实和功能语义的主要来源。
2. `doc/` 下三个改造文档是 Python 化迁移蓝图。
3. 当前 Python 生态、可测试性、可维护性和用户学习目标决定最终落地方式。

如果 Java 原项目、改造文档和 Python 最佳实践之间发生冲突，助手应：

- 先指出冲突点。
- 说明继续照搬的风险。
- 给出更适合 Python/FastAPI/SQLAlchemy/LangGraph 生态的方案。
- 对影响较大的架构取舍，先解释后推进；对小的工程修正可直接采用并说明原因。

不要机械照搬 Java，也不要盲从 doc 里的设计。目标是保留原业务语义，同时做出更自然、更可测、更适合面试表达的 Python 版实现。

## 技术栈方向

后端：

- Python `>=3.10`
- FastAPI
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2.0 async
- Alembic
- pytest / pytest-asyncio / httpx

大模型：

- 通义千问 DashScope / 阿里云百炼
- 推荐使用 OpenAI-compatible 协议
- 生成模型：`qwen-plus`
- 快速任务模型：`qwen-turbo` 或 `qwen-flash`
- Embedding：`text-embedding-v4`

RAG：

- LangChain
- LangGraph
- Milvus
- Elasticsearch
- Neo4j
- BGE reranker 或可替换 reranker 封装

工程组件：

- MySQL
- Redis
- MinIO
- Celery
- Docker Compose

## 建议目录

当前 PyCharm 项目根目录是 `/Users/fantasy/code/konw-engine`。虚拟环境、`pyproject.toml`、`uv.lock` 统一放在根目录；Python 源码和测试放在 `know_engine_py/` 内，避免和 `res/`、`doc/` 混在一起：

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
└── README.md
```

根目录保留：

```text
.venv/
pyproject.toml
uv.lock
```

不要在 `know_engine_py/` 下再创建 `.venv`、`pyproject.toml` 或 `uv.lock`。

## 带学协作方式

每个模块按 7 步推进：

1. 对照 Java 版：说明 Java 中对应类、方法、职责。
2. Python 化设计：说明 FastAPI / SQLAlchemy / LangGraph 里如何表达。
3. 说明当前功能需要哪些文件、为什么按这个目录组织、每个文件承担什么职责。
4. 讲清相关 Python 语法和框架语法，再给文件骨架。
5. 用户手敲核心逻辑。
6. Review：检查命名、异步写法、事务、异常、类型、测试。
7. 跑验证命令：每天必须留下可运行结果。
8. 沉淀面试点：整理成 3-5 句话。

后续带学时，每个新功能至少覆盖：

- 当前代码实现了什么功能。
- 涉及哪些 Python 语法，例如包导入、装饰器、类型注解、类继承、缓存装饰器、异步语法等。
- 涉及哪些框架概念，例如 FastAPI router、Pydantic Settings、SQLAlchemy Session、LangGraph node 等。
- 为什么需要这些文件，而不是写在一个文件里。
- 当前文件组织结构和 Java/Spring 项目分层的对应关系。
- 给任务时应提供完整文件清单和必要脚手架，避免把“模块不存在、缺 `__init__.py`、目录没创建”这类基础错误当作教学重点。
- 给新文件时必须写清楚绝对路径、所属目录、是否需要新建目录、文件职责、为什么放在这里、对应 Java/Spring 哪一层；不要只给一个裸文件名。
- 给业务性代码前必须先讲清楚：这个文件/类/方法的职责、完整执行流程、关键代码为什么这样写、和上下游模块如何协作；不要一上来整段贴代码。
- 对超过 30 行的业务代码，应拆成“流程说明 + 分段代码 + 分段解释 + 用户手敲范围”，避免让用户复制代码后再去问其他模型解释。
- TDD 仍然使用，但 RED 阶段优先验证行为不满足，而不是依赖缺文件导致的导入失败。
- 提供代码时，在关键设计处添加简洁注释，解释非显而易见的原因；不要给每一行都写说明性废话。

### 注释和 docstring 约定

为了兼顾 Python 项目整洁性和用户学习需要，后续代码示例应使用“必要 docstring + 少量关键注释”的风格：

- 公开 Service 类、复杂业务方法、FastAPI router 方法、核心 LangGraph node、重要工具函数，应写 Python docstring。
- docstring 说明“这个方法做什么、业务规则是什么、返回什么、什么时候 fallback 或抛错”，类似 JavaDoc 的职责说明。
- 简单的 `__init__`、纯字段 ORM、显而易见的一行 getter，不强制写 docstring。
- 代码内部只在非显而易见处写简洁注释，例如缓存 key、事务边界、SQLAlchemy 保留字段、fallback 策略。
- 避免把代码翻译成中文注释，例如“给变量赋值”“执行查询”这类低价值注释不要写。

示例：

```python
async def get_intent_or_fallback(
    self,
    domain_id: str,
    intent_name: str,
) -> IntentConfigModel | None:
    """查询指定意图；如果不存在，则返回当前领域配置的 fallback 意图。"""
```

每天结束时，将知识要点沉淀到单独学习笔记，不写入进度文档：

- 学习笔记路径：`doc/learning_notes/dayN_<topic>.md`
- 学习笔记内容：功能说明、文件职责、组织架构原因、Python 语法、框架概念、Java 对照、验证命令、面试可讲点。
- `doc/progress_tracker.md` 只保留干脆的进度、状态、下一步和阻塞点，避免被长篇知识点污染。

用户每天可以这样开始：

```text
开始 Day N，先带我做第一个任务。
```

然后应按当天计划推进，不要跳太远。

## 哪些代码应优先让用户手敲

学习收益最高，尽量不要一键生成完整实现：

- FastAPI router 和 dependency
- Pydantic schema
- SQLAlchemy model 和 query
- Service 层业务逻辑
- LangGraph `AgentState` 和各个 node
- SSE streaming generator
- 测试用例

对这些“应手敲”的内容，助手不要直接在项目中创建或改写最终文件，除非用户明确要求代写。应先在回复中提供：

- 文件路径
- 绝对路径、所属目录、是否需要新建目录
- 文件职责
- 为什么放在这个目录，以及对应 Java/Spring 哪一层
- 当前文件/类/方法的职责
- 业务流程步骤
- 关键代码解释，尤其是异步、事务、查询、fallback、upsert、依赖注入等不直观部分
- 代码骨架或核心代码片段
- 每段代码的设计原因
- 需要用户手敲的范围
- 运行命令
- 预期结果和常见错误

用户手敲完成并反馈测试结果或代码片段后，再进行 review、排错和必要的小范围修补。

核心协作原则：

> 架子助手搭，核心用户写；字段助手搬，逻辑用户练。

## 哪些代码可以由助手多给一点

偏机械或耗时，可给完整初稿，再让用户阅读微调：

- Docker Compose
- Alembic 初始配置
- 枚举和常量平移
- README 结构
- 简单工具类
- 种子 YAML
- Makefile 或常用脚本

## 10 天节奏

Day 1：项目骨架与运行闭环

- `pyproject.toml`
- `app/main.py`
- `app/core/settings.py`
- `/health`
- 第一个接口测试

Day 2：数据库模型与动态配置表

- SQLAlchemy async
- BaseEntity
- domain / intent / prompt
- chat / document 核心模型

Day 3：配置服务、Prompt 服务和 Admin API

- DomainConfigService
- PromptService
- automotive seed YAML
- Admin CRUD

Day 4：文档上传、解析入口和切分

- MinIO 封装
- Markdown/txt 解析
- splitter
- document process service

Day 5：Embedding、Milvus、Elasticsearch 和混合检索

- DashScope embedding
- Milvus 写入与检索
- ES BM25
- RRF 融合

Day 6：LangGraph 基础 RAG 状态机

- AgentState
- intent / transform / router / retrieve / generate
- common chat 分支

Day 7：Rerank、Grader、Rewrite 和 Corrective RAG

- reranker
- grader
- rewrite
- retry loop
- prompt select

Day 8：聊天会话、消息持久化和 SSE

- conversation service
- message service
- `/chat/send`
- `[PROGRESS]` / `[REFERENCE]` / `[DONE]`

Day 9：Celery、MinerU、Neo4j 和工程补强

- Celery worker
- document async task
- MinerU client
- Neo4j retriever

Day 10：测试、部署、README 和面试材料

- Docker Compose
- `.env.example`
- smoke tests
- README
- `doc/interview_talking_points.md`

## DashScope 接入约定

`.env` 建议：

```env
DASHSCOPE_API_KEY=your-api-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_CHAT_MODEL=qwen-plus
LLM_FAST_MODEL=qwen-turbo
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
```

封装目标：

- `LLMService.chat()`
- `LLMService.fast_chat()`
- `EmbeddingService.embed_query()`
- `EmbeddingService.embed_documents()`

业务代码只依赖 service，不直接散落 DashScope SDK 或 API key。

## Git 提交规范

后续由助手执行 Git 提交时，提交信息使用中文描述，但格式遵循 Conventional Commits：

```text
<type>(<scope>): <中文摘要>
```

常用 `type`：

- `feat`：新增功能
- `fix`：修复问题
- `docs`：文档更新
- `test`：测试相关
- `refactor`：重构，不改变外部行为
- `chore`：工程配置、依赖、脚本等杂项

示例：

```text
feat(document): 增加文档切分服务
fix(prompt): 修复意图识别模板变量渲染
docs: 记录中文提交信息规范
test(admin): 补充 Prompt 管理接口测试
```

提交摘要要求：

- 使用中文，简洁说明本次提交做了什么。
- 不写空泛描述，例如“更新代码”“修改文件”。
- 一次提交只覆盖一个相对清晰的主题，避免把无关改动混在一起。
- 如果提交涉及敏感配置或付费闭源参考资料，提交前必须确认 `.env`、`res/`、`local_private/` 等目录未被纳入 Git。

## 进度维护要求

每完成一个任务或发生计划调整时，更新：

- `doc/progress_tracker.md`

更新内容至少包括：

- 当前状态
- 已完成
- 正在进行
- 下一步
- 阻塞点
- 当日学习点
- 当日面试可讲点

如果新窗口启动，应先阅读本文件、`doc/progress_tracker.md` 和最近一天的 `doc/learning_notes/dayN_*.md`，再继续推进。
