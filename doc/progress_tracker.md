# Know-Engine Python 改造进度跟踪

> 更新时间：2026-05-10
>
> 当前阶段：Day 4 开始
>
> 协作方式：带学式结对开发。用户手敲核心代码，助手负责讲解、拆任务、给骨架、review、排错、补测试思路和面试表达。
>
> 进度文档只记录状态、任务、下一步和阻塞点；知识要点沉淀到 `doc/learning_notes/`。

## 1. 当前目标

基于 Java 版 `res/LLMentor/know-engine`，在当前仓库中实现 Python 版 Know-Engine RAG 项目。

项目路径建议：`know_engine_py/`

环境约定：

- PyCharm 项目根目录是 `/Users/fantasy/code/konw-engine`。
- 只使用根目录 `.venv`。
- `pyproject.toml` 和 `uv.lock` 放在根目录。
- 不在 `know_engine_py/` 下创建子虚拟环境。

10 天总目标：

- FastAPI 应用骨架
- SQLAlchemy async ORM
- 动态领域配置和 Prompt 管理
- 文档处理与切分
- DashScope embedding
- Milvus + Elasticsearch + Neo4j 多源检索
- LangGraph Corrective RAG 状态机
- SSE 流式聊天
- Celery 异步任务
- Docker Compose
- README 和面试材料

## 2. 已完成

- 阅读并理解用户背景：
  - 用户是 Java 后端开发者。
  - 已学习 Python 基础语法。
  - 希望转型 Python 大模型应用开发方向。
  - 希望通过手敲/半手敲加强学习和记忆。
- 阅读已有规划文档：
  - `doc/migration_plan_final.md`
  - `doc/implementation_blueprint.md`
  - `doc/implementation_blueprint_part2.md`
- 确认技术路线：
  - 不缩水为简单 demo。
  - 以 10 天、每天约 8 小时为节奏。
  - 目标不砍模块，但按“先跑通、再加厚、再包装”分层交付。
- 确认大模型供应商：
  - 使用通义千问 DashScope / 阿里云百炼。
  - 推荐使用 OpenAI-compatible 协议。
  - 生成模型建议 `qwen-plus`。
  - 快速任务模型建议 `qwen-turbo` 或 `qwen-flash`。
  - Embedding 建议 `text-embedding-v4`。
- 已生成 10 天带学计划：
  - `doc/10_day_full_sprint_learning_plan.md`
- 已生成新窗口交接说明：
  - `AGENTS.md`
- 已生成本进度跟踪文档：
  - `doc/progress_tracker.md`
- 已调整 Python 环境布局：
  - 保留根目录 `.venv`
  - 将 `pyproject.toml` 放到根目录
  - 删除误生成的 `know_engine_py/.venv`
  - 删除误生成的 `know_engine_py/uv.lock`
  - 测试导入改为 `from know_engine_py.app.main import app`
- 已确认后续带学要求：
  - 说明当前功能做什么
  - 说明相关 Python 语法和框架语法
  - 说明为什么需要这些文件
  - 说明文件组织架构为什么这样设计
  - 提供完整文件清单和必要脚手架
  - 不把基础模块缺失问题作为教学重点
  - 关键设计处需要加简洁注释
- 已确认文档分工：
  - `doc/progress_tracker.md` 只记录干脆进度
  - `doc/learning_notes/` 记录每日知识沉淀
- 已确认手敲优先规则：
  - 需要用户练习的核心逻辑不直接落盘
  - 助手提供路径、职责、骨架、讲解、验证命令和常见错误
  - 用户手敲后再 review、排错和小范围修补
- 已确认中间件环境：
  - 使用用户自有云服务器上已启动的 MySQL / Redis / MinIO / Elasticsearch
  - MySQL 当前只使用 `root` 用户
  - 普通单元测试继续使用 SQLite，远程 MySQL 只通过显式集成测试验证
- 已完成远程 MySQL 集成验证：
  - `MYSQL_TEST_DATABASE_URL` 通过 `Settings` 从 `.env` 读取
  - `uv run pytest know_engine_py/tests/test_mysql_integration.py -q` 已通过
- 已完成聊天会话模型：
  - `chat_conversation`
  - `chat_message`
  - 覆盖会话默认状态、消息 JSON 引用、`metadata` 保留字段映射
- 已完成文档核心模型：
  - `knowledge_document`
  - `knowledge_segment`
  - `table_meta`
  - 覆盖文档扩展字段、切片排序、表字段 JSON 信息
- 已创建 Day 2 学习笔记：
  - `doc/learning_notes/day2_database_models.md`
- 已完成 Day 3 配置服务基础能力：
  - `DomainConfigService`
  - `PromptService`
  - `SeedService`
  - automotive 领域包 YAML 与公开示例 Prompt 初始化
  - Admin Domain API
  - Admin Intent API
  - Admin Prompt API
  - Prompt 动态构建兼容完整 Prompt 与占位符模板
  - 全量测试：`uv run pytest know_engine_py/tests -q`，结果 `26 passed`
- 已创建 Day 3 学习笔记：
  - `doc/learning_notes/day3_config_prompt_admin.md`

## 3. 正在进行

正在进行 Day 4：文档上传、解析入口和切分。

Day 4 当前目标：

- 建立文档上传/导入入口
- 先跑通 Markdown/txt 解析与切分
- 保存 `knowledge_document` 和 `knowledge_segment`
- 预留 MinIO 与 MinerU 客户端边界
- 为 splitter 和文档处理服务编写行为测试

## 4. 下一步任务

当前下一步：

- Day 4 第一个任务：设计并测试 Markdown/txt `DocumentSplitter`

## 5. 总任务看板

### Day 1：项目骨架与运行闭环

状态：完成

任务：

- [x] 创建 `know_engine_py/` 项目目录
- [x] 创建 `pyproject.toml`
- [x] 创建 `app/main.py`
- [x] 创建 `app/core/settings.py`
- [x] 创建 `app/api/health_router.py`
- [x] 创建 `tests/test_health.py`
- [x] 验证 health 测试 RED 状态，当前失败原因：`ModuleNotFoundError: No module named 'app'`
- [x] 整理 PyCharm/uv 环境布局，统一使用根目录 `.venv`
- [x] 验证新 RED 状态，当前失败原因：`ModuleNotFoundError: No module named 'know_engine_py'`
- [x] 在 pytest 配置中加入 `pythonpath = ["."]`
- [x] 跑通 `/health`
- [x] 跑通测试：`uv run pytest know_engine_py/tests/test_health.py -q`
- [x] 创建 `tests/test_settings.py`
- [x] 验证环境变量可覆盖默认配置：`uv run pytest know_engine_py/tests -q`，结果 `2 passed`
- [x] 创建 `.env.example`
- [x] 启动本地 FastAPI 服务：`uv run uvicorn know_engine_py.app.main:app --reload`
- [x] 手动访问 `/health`，返回应用状态和模型配置摘要
- [x] 创建 Day 1 学习笔记：`doc/learning_notes/day1_foundation.md`

### Day 2：数据库模型与动态配置表

状态：完成

任务：

- [x] SQLAlchemy async session
- [x] ORM BaseEntity
- [x] domain_config 模型
- [x] intent_config 模型
- [x] prompt_template 模型
- [x] 远程 MySQL 集成验证
- [x] chat_conversation / chat_message 模型
- [x] knowledge_document / knowledge_segment / table_meta 模型
- [x] 基础 CRUD 测试

### Day 3：配置服务、Prompt 服务和 Admin API

状态：完成

任务：

- [x] DomainConfigService
- [x] PromptService 查询模板、fallback、最新版本和动态意图识别 Prompt
- [ ] Redis 缓存和失效（延后到配置读写频繁后再加）
- [x] automotive seed YAML 领域包结构
- [x] prompt txt 初始化
- [x] SeedService 领域包导入
- [x] Admin domain API
- [x] Admin intent API
- [x] Admin prompt API
- [x] Prompt 动态拼装测试

### Day 4：文档上传、解析入口和切分

状态：进行中

任务：

- [ ] FileStorageService
- [ ] FileProcessService
- [ ] Markdown/txt processor
- [ ] MinerU client 接口占位
- [ ] DocumentSplitter
- [ ] DocumentProcessService
- [ ] Document API
- [ ] Splitter 测试

### Day 5：Embedding、Milvus、Elasticsearch 和混合检索

状态：未开始

任务：

- [ ] DashScope EmbeddingService
- [ ] Milvus 写入
- [ ] Milvus Retriever
- [ ] Elasticsearch 索引
- [ ] ES Keyword Retriever
- [ ] RRF 融合
- [ ] Hybrid Retriever
- [ ] 检索测试

### Day 6：LangGraph 基础 RAG 状态机

状态：未开始

任务：

- [ ] AgentState
- [ ] intent_node
- [ ] transform_node
- [ ] router_node
- [ ] retriever_node
- [ ] generator_node
- [ ] common_chat_node
- [ ] graph.py
- [ ] graph smoke test

### Day 7：Rerank、Grader、Rewrite 和 Corrective RAG

状态：未开始

任务：

- [ ] reranker_node
- [ ] grader_node
- [ ] rewrite_node
- [ ] prompt_select_node
- [ ] LangGraph 循环边
- [ ] 最大重试次数
- [ ] Corrective RAG 测试

### Day 8：聊天会话、消息持久化和 SSE

状态：未开始

任务：

- [ ] ChatConversationService
- [ ] ChatMessageService
- [ ] TitleSummaryService
- [ ] Chat API
- [ ] SSE streaming generator
- [ ] `[PROGRESS]`
- [ ] `[REFERENCE]`
- [ ] `[DONE]`
- [ ] 消息回写测试

### Day 9：Celery、MinerU、Neo4j 和工程补强

状态：未开始

任务：

- [ ] Celery app
- [ ] 文档异步任务
- [ ] 补偿任务
- [ ] MinerU 在线 API client
- [ ] Neo4j Retriever
- [ ] retriever_node 接入图谱检索
- [ ] 外部服务失败 fallback

### Day 10：测试、部署、README 和面试材料

状态：未开始

任务：

- [ ] Docker Compose
- [ ] `.env.example`
- [ ] 冒烟测试
- [ ] README
- [ ] 架构图
- [ ] API 说明
- [ ] `doc/interview_talking_points.md`
- [ ] 最终演示脚本

## 6. 当前阻塞点

暂无。

潜在风险：

- 外部服务多，Docker 联调可能耗时。
- Python async、SQLAlchemy async、LangGraph 对用户较新，需要边写边讲。
- DashScope API key 和本地服务配置需要用户准备。

## 7. 学习记录

### 2026-05-04

学习点：

- 10 天全量目标应采用“先闭环、再加厚”的工程策略。
- 不应把 MVP 理解为缩水，而应理解为早期可运行里程碑。
- 模型服务建议通过 OpenAI-compatible 协议抽象，避免业务代码绑定供应商 SDK。
- Day 1 已进入 TDD 的 RED 阶段：先写 `/health` 测试，再实现 FastAPI app。
- Day 1 已验证 `pydantic-settings` 可通过环境变量覆盖默认值，对应 Spring Boot 配置覆盖能力。
- Day 1 已完成真实 HTTP 验证：`GET /health` 返回 `200 OK`。
- 后续讲解需要显式覆盖“功能、语法、文件职责、组织架构原因、Java 对照”。

面试可讲点：

- Java 版 RAG 管道升级为 Python LangGraph 状态机。
- 汽车领域硬编码升级为 DB 动态配置。
- DashScope 接入通过模型服务封装实现供应商可替换。

### 2026-05-10

学习点：

- Day 3 已完成领域、意图、Prompt 的数据库配置闭环。
- Prompt 分为意图识别、业务意图 chat、未来 common chat 三类使用场景。
- `SeedService` 使用 `flush()`，把事务提交或回滚交给调用方控制。
- 动态 Prompt 当前兼容完整文本和轻量占位符替换，暂不引入 Jinja2。
- Admin API 使用 FastAPI Router、`Depends(get_db)`、Pydantic `from_attributes` 对应 Spring Controller、依赖注入和 DTO/VO。

面试可讲点：

- 将 Java 项目里硬编码的领域、意图和 Prompt 升级为 `domain_config`、`intent_config`、`prompt_template` 三层动态配置。
- Prompt 服务按领域、意图、类型和版本选择最新启用模板，并通过 fallback 意图兜底。
- 领域包导入机制支持 YAML 和 prompt txt 初始化行业配置，后续可通过 Admin API 维护。

## 8. 新窗口恢复步骤

如果开新窗口或上下文丢失，请先按顺序阅读：

1. `AGENTS.md`
2. `doc/progress_tracker.md`
3. 最近一天的 `doc/learning_notes/dayN_*.md`
4. `doc/10_day_full_sprint_learning_plan.md`
5. 必要时再查：
   - `doc/migration_plan_final.md`
   - `doc/implementation_blueprint.md`
   - `doc/implementation_blueprint_part2.md`

然后继续当前 `正在进行` 和 `下一步任务`。
