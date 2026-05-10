# Day 2 学习笔记：SQLAlchemy Async 与核心数据模型

## 1. 当天目标

Day 2 的目标是把 Java 版 Know-Engine 的核心数据表迁移成 Python ORM 模型，并完成数据库访问闭环。

当天完成内容：

- 接入 SQLAlchemy 2.0 async。
- 创建数据库 session 工厂。
- 抽取 ORM 公共基类 `BaseEntity`。
- 迁移动态配置表：
  - `domain_config`
  - `intent_config`
  - `prompt_template`
- 迁移聊天会话表：
  - `chat_conversation`
  - `chat_message`
- 迁移文档相关表：
  - `knowledge_document`
  - `knowledge_segment`
  - `table_meta`
- 使用 SQLite 做快速 CRUD 测试。
- 使用云服务器 MySQL 做显式集成测试。

对应 Java/Spring 能力：

- `DataSource` / MyBatis-Plus `Mapper`
- `BaseEntity`
- Java entity class
- MySQL 表结构
- Service 层未来会基于这些模型做 CRUD 和业务编排

## 2. 当前文件职责

```text
know_engine_py/app/
├── core/
│   └── settings.py
├── db/
│   └── session.py
└── models/
    ├── base.py
    ├── config.py
    ├── chat.py
    ├── document.py
    └── __init__.py

know_engine_py/tests/
├── test_db_session.py
├── test_base_model.py
├── test_config_models.py
├── test_config_models_crud.py
├── test_chat_models_crud.py
├── test_document_models_crud.py
└── test_mysql_integration.py
```

### `core/settings.py`

负责统一读取配置，类似 Spring Boot 的 `application.yml + @ConfigurationProperties`。

本日新增数据库配置：

- `database_url`
- `database_echo`
- `mysql_test_database_url`

为什么不用到处 `os.getenv()`：

- `Settings` 是统一配置入口。
- 字段、默认值、类型都集中声明。
- `.env` 由 `pydantic-settings` 读取。
- 测试时可以用 `get_settings.cache_clear()` 清理缓存。

### `db/session.py`

负责创建 SQLAlchemy async session。

核心职责：

- 根据数据库连接串创建 async engine。
- 根据 engine 创建 `async_sessionmaker`。
- 给 FastAPI dependency 预留 `get_db()`。
- 避免 import 时就创建数据库连接。

关键设计：

```python
@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()
    return create_session_maker(settings.database_url, settings.database_echo)
```

为什么延迟初始化：

- Python import 会执行模块顶层代码。
- 如果在模块顶层直接创建 engine，测试改环境变量也来不及。
- 延迟到第一次调用 `get_session_maker()` 时读取配置，更接近 Spring 容器启动后按配置初始化 bean。

### `models/base.py`

负责定义所有 ORM 模型共享的基类。

- `Base`：SQLAlchemy 声明式基类，负责收集所有表的 metadata。
- `BaseEntity`：公共字段 mixin。

公共字段：

- `created_at`
- `updated_at`
- `lock_version`
- `deleted`

Java 对照：

- `Base` 类似 MyBatis-Plus 能识别实体元数据的基础设施。
- `BaseEntity` 对应 Java 版 `BaseEntity`。

### `models/config.py`

动态配置模型。

这些表服务于“领域 + 意图 + Prompt 配置化”：

- `DomainConfigModel`：一个业务领域，例如汽车。
- `IntentConfigModel`：领域下的意图，例如售前咨询、故障诊断。
- `PromptTemplateModel`：不同领域、意图、类型、版本对应的 Prompt。

后续 Day 3 会基于这些模型写：

- `DomainConfigService`
- `PromptService`
- Admin CRUD API

### `models/chat.py`

聊天会话模型。

- `ChatConversationModel`：会话主表，类似聊天软件左侧会话列表。
- `ChatMessageModel`：消息明细表，保存用户消息、AI 回复、模型名、token、RAG 引用。

后续 Day 8 会基于这些模型写：

- 会话创建
- 历史消息查询
- `/chat/send`
- SSE 流式返回完成后的 assistant 消息落库

注意点：

```python
extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
```

`metadata` 是 SQLAlchemy 的保留属性，不能直接作为 ORM 属性名。  
所以 Python 属性叫 `extra_metadata`，数据库列名仍然映射为 `metadata`。

### `models/document.py`

文档相关模型。

- `KnowledgeDocumentModel`：文档主记录。
- `KnowledgeSegmentModel`：文档切片。
- `TableMetaModel`：结构化数据动态建表的元信息。

后续 Day 4 / Day 5 会基于这些模型写：

- 文件上传
- Markdown/txt 解析
- 文本切分
- embedding
- Milvus / Elasticsearch 检索

Python 化调整：

Java 版里 `extension`、`metadata`、`columns_info` 多数是 JSON 字符串。  
Python 版直接用 SQLAlchemy `JSON` 类型映射为 `dict` 或 `list[dict]`。

收益：

- 业务层不用反复 `json.loads()` / `json.dumps()`。
- Pydantic schema 也更容易表达结构化字段。

## 3. SQLAlchemy 关键语法

### `DeclarativeBase`

```python
class Base(DeclarativeBase):
    pass
```

这是 SQLAlchemy 2.0 声明式 ORM 的基类。所有继承 `Base` 的模型都会被收集到 `Base.metadata`。

测试里创建表：

```python
await conn.run_sync(Base.metadata.create_all)
```

### `Mapped` 和 `mapped_column`

```python
doc_title: Mapped[str] = mapped_column(String(1024), nullable=False)
```

含义：

- `Mapped[str]`：告诉 SQLAlchemy 和类型检查器，这是一个 ORM 映射字段。
- `mapped_column(...)`：声明数据库列类型、是否允许为空、默认值、索引等。

### 可空类型

```python
description: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

`str | None` 是 Python 3.10+ 的联合类型语法，表示这个字段可能是字符串，也可能是空。

Java 对照：

```java
private String description;
```

Java 里引用类型默认可为 null；Python 里通过类型注解明确表达。

### 表名

```python
__tablename__ = "knowledge_document"
```

指定 ORM 类映射哪张表。  
类似 Java MyBatis-Plus 的：

```java
@TableName("knowledge_document")
```

### 索引和唯一约束

```python
__table_args__ = (
    UniqueConstraint("domain_id", "intent_name", name="uk_domain_intent"),
    Index("idx_knowledge_segment_document_order", "document_id", "chunk_order"),
)
```

用途：

- 唯一约束保证业务唯一性。
- 索引服务查询性能。

注意：

Day2 只是声明模型和测试行为，后续引入 Alembic 后才会负责迁移真实 MySQL 表结构。

### async session

```python
async with session_maker() as session:
    result = await session.execute(select(Model))
```

要点：

- `async with` 自动管理 session 生命周期。
- `await` 等待数据库 IO。
- `session.execute()` 返回结果对象。
- `scalar_one()` 取唯一一行 ORM 对象。
- `scalars().all()` 取多行 ORM 对象列表。

## 4. SQLite 与 MySQL 差异

Day2 遇到过一个很典型的问题：

SQLite 只有 `INTEGER PRIMARY KEY` 会自动使用 rowid 自增。  
`BigInteger primary_key autoincrement` 在 SQLite 下不会像 MySQL 的 `BIGINT AUTO_INCREMENT` 一样工作。

因此当前模型主键使用 `Integer`。

原因：

- Day2 的本地快速测试用 SQLite。
- 配置表、会话表、文档表在练习项目里数据量不大。
- 先保证跨 SQLite / MySQL 的开发体验稳定。

后续如果需要严格对齐 MySQL `BIGINT`，可以在 Alembic 阶段使用方言相关类型或 variant。

## 5. MySQL 集成测试

普通测试继续使用 SQLite：

```bash
uv run pytest know_engine_py/tests -q
```

远程 MySQL 集成测试通过 `.env` 中的：

```env
MYSQL_TEST_DATABASE_URL=mysql+asyncmy://root:your-password@your-mysql-host:3306/know_engine?charset=utf8mb4
```

测试入口：

```bash
uv run pytest know_engine_py/tests/test_mysql_integration.py -q
```

为什么分开：

- 单元测试要快、稳定、不依赖远程服务。
- 集成测试验证真实驱动、真实网络、真实 MySQL。
- 没配置连接串时自动跳过，避免影响普通开发。

## 6. 文件组织和 Java 对照

Python 分层：

```text
app/core/settings.py        配置
app/db/session.py           数据库连接和 session
app/models/*.py             ORM 实体
tests/test_*_crud.py        行为测试
```

Java/Spring 对照：

```text
application.yml             -> settings.py
DataSourceConfig            -> db/session.py
entity/*.java               -> models/*.py
Mapper + Service CRUD 验证   -> tests/test_*_crud.py
```

为什么模型按主题拆文件：

- `config.py`：领域、意图、Prompt。
- `chat.py`：聊天会话和消息。
- `document.py`：文档、分片、结构化表。

这样后续服务层也能按领域组织：

- `services/config_service.py`
- `services/chat_service.py`
- `services/document_service.py`

## 7. 当日验证命令

```bash
uv run pytest know_engine_py/tests/test_db_session.py -q
uv run pytest know_engine_py/tests/test_config_models_crud.py -q
uv run pytest know_engine_py/tests/test_mysql_integration.py -q
uv run pytest know_engine_py/tests/test_chat_models_crud.py -q
uv run pytest know_engine_py/tests/test_document_models_crud.py -q
uv run pytest know_engine_py/tests -q
```

当前全量结果：

```text
13 passed
```

## 8. 面试可讲点

可以这样表达 Day2：

1. 我用 SQLAlchemy 2.0 async 重建了 Java 项目的核心 ORM 模型，并把数据库 session 做成延迟初始化，避免 import 阶段读取错误配置。
2. 动态配置表用于把领域、意图和 Prompt 从代码硬编码迁移到数据库配置，为后续 PromptService 和 Admin API 打基础。
3. 聊天会话表和消息表支持历史消息、模型调用记录、RAG 引用持久化，后续可以接 SSE 流式返回。
4. 文档表、切片表和表元数据表支撑文档处理、embedding、混合检索和结构化数据查询。
5. 单元测试用 SQLite 保证快速反馈，显式集成测试用 asyncmy 连接远程 MySQL 验证真实环境。

## 9. 后续复盘建议

建议重点手敲：

- `db/session.py`
- 一个简单 ORM 模型，例如 `DomainConfigModel`
- 一个复杂 ORM 模型，例如 `KnowledgeSegmentModel`
- 一个 CRUD 测试，例如 `test_document_models_crud.py`

不建议反复机械手敲所有字段。  
更好的方式是：先理解一类字段，再自己写一个模型和测试，最后对照现有代码修正。
