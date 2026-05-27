# Know-Engine Python

基于 Java 版 Know-Engine 改造的 Python RAG 知识库问答系统。

本项目不是一个只调用 LangChain 的简单 demo，而是围绕真实知识库平台常见链路做 Python 化重建：文档上传、解析、切分、异步任务、混合检索、Corrective RAG、Text-to-SQL、会话消息、SSE 输出和后续工程化部署。

## 当前定位

当前版本处于 v0.1 企业级工程化发布冲刺阶段。

已经完成的主链路：

- FastAPI 应用骨架和配置加载。
- SQLAlchemy async ORM。
- 领域、意图、Prompt 数据库配置化。
- 文档导入、解析、切分、segment 落库。
- MinIO / FileStorage 边界。
- Celery 文档索引、转换和补偿任务入口。
- LangChain Document / Embeddings / VectorStore / Retriever 边界。
- Milvus、Elasticsearch、Hybrid Retriever 设计。
- LangGraph RAG 状态机。
- Rerank、Grader、Rewrite、Reference。
- Text-to-SQL 第一阶段：表元数据、SQL 安全、只读执行、结果格式化和 fallback。
- Chat 会话、消息持久化和 SSE frame 输出。

v0.1 正在补齐：

- 部署脚手架和分层健康检查。
- JWT 认证、群组、知识库权限隔离。
- 分片上传、秒传、断点续传。
- ETL 任务状态、重试、补偿和观测。
- 真实中间件 smoke。
- 检索质量评估。
- 极简前端和在线演示。

暂不阻塞 v0.1：

- mem0 长期记忆。
- Neo4j / Text-to-Cypher。
- 复杂 Agent 工具体系。

## 技术栈

- Python 3.10+
- FastAPI
- SQLAlchemy async
- Pydantic Settings
- LangChain / LangGraph
- Milvus
- Elasticsearch
- Redis
- MinIO
- Celery
- DashScope OpenAI-compatible API
- pytest / pytest-asyncio

## 项目结构

```text
know_engine_py/
├── app/
│   ├── api/          # FastAPI router
│   ├── core/         # settings 等基础设施
│   ├── db/           # 数据库 session
│   ├── models/       # SQLAlchemy ORM
│   ├── rag/          # splitter / retriever / LangGraph node / SQL RAG
│   ├── schemas/      # Pydantic request/response
│   ├── services/     # 应用业务编排
│   ├── storage/      # FileStorage / MinIO adapter
│   └── tasks/        # Celery task
├── config/
│   └── domains/      # 领域配置和 Prompt
└── tests/
```

## 快速启动

### 1. 安装依赖

```bash
uv sync
```

### 2. 准备配置

```bash
cp .env.example .env
```

然后按你的环境修改 `.env`。真实密钥和远程中间件密码只放 `.env`，不要提交。

### 3. 启动 API

```bash
make dev
```

或：

```bash
uv run fastapi dev know_engine_py/app/main.py
```

### 4. 运行测试

```bash
make test
```

等价于：

```bash
uv run pytest know_engine_py/tests -q
```

### 5. 启动 Celery Worker

需要先配置 Redis：

```bash
make worker
```

等价于：

```bash
uv run celery -A know_engine_py.app.tasks.celery_app.celery_app worker -l info
```

## Docker Compose

先准备 `.env`：

```bash
cp .env.example .env
```

启动 API 和 worker：

```bash
docker compose up --build api worker
```

如果需要本地中间件，可启用 profile：

```bash
docker compose --profile local-middleware up --build
```

说明：如果你使用云服务器上的 MySQL / Redis / MinIO / Elasticsearch，可以只启动 `api` 和 `worker`，中间件地址写在 `.env`。

## 常用命令

```bash
make dev      # 本地启动 FastAPI 开发服务
make test     # 运行测试
make worker   # 启动 Celery worker
make smoke    # 做轻量导入和配置检查
```

## 健康检查

基础健康检查：

```bash
curl http://127.0.0.1:8000/health
```

默认只做轻量分层状态，不主动连接 Redis、MinIO、Elasticsearch 等外部服务。真实连通性检查用于 smoke 或人工排障：

```bash
curl "http://127.0.0.1:8000/health?deep=true"
```

当前分层：

- app
- database
- redis
- minio
- elasticsearch
- llm

## 当前进度

Day10 以后的主计划和进度维护在：

```text
doc/12_day_enterprise_engineering_release_plan.md
```

Day1-Day9 历史摘要在：

```text
doc/progress_tracker.md
```

## 项目边界说明

本项目用于学习和面试展示，不声称已经生产落地。当前目标是做出一个工程化 v0.1：能部署、能演示、能解释关键设计、能经得起代码和架构追问。
