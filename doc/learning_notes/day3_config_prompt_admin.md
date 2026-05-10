# Day 3 学习笔记：配置服务、Prompt 服务与 Admin API

## 1. 当天目标

Day 3 的目标是把 Day 2 建好的配置表真正用起来，形成“领域、意图、Prompt 可配置”的服务层和后台查询接口。

当天完成内容：

- `DomainConfigService`
- `PromptService`
- `SeedService`
- automotive 领域包 YAML 与公开示例 Prompt 初始化
- Admin Domain API
- Admin Intent API
- Admin Prompt API
- Prompt 动态构建兼容完整 Prompt 与占位符模板

对应 Java/Spring 能力：

- `Controller`
- `Service`
- `Entity`
- `DTO/VO`
- `@Autowired` / 依赖注入
- 初始化配置导入

## 2. 当前文件职责

```text
know_engine_py/app/
├── api/
│   ├── admin_domain_router.py
│   ├── admin_intent_router.py
│   └── admin_prompt_router.py
├── schemas/
│   ├── domain.py
│   ├── intent.py
│   └── prompt.py
└── services/
    ├── domain_config_service.py
    ├── prompt_service.py
    └── seed_service.py

know_engine_py/config/domains/
├── automotive.yaml
└── automotive/prompts/*.txt
```

### `DomainConfigService`

负责读取领域和意图配置。

核心方法：

- `get_active_domain()`
- `list_active_intents(domain_id)`
- `get_intent_or_fallback(domain_id, intent_name)`
- `list_domains()`
- `get_domain_by_id(domain_id)`
- `list_intents_by_domain(domain_id)`

Java 对照：`DomainConfigService` / `IntentConfigService`。

### `PromptService`

负责读取和选择 Prompt。

核心方法：

- `get_prompt(domain_id, intent_name, prompt_type)`
- `_get_active_prompt_template(...)`
- `build_intent_recognition_prompt()`
- `list_prompt_templates(...)`

关键规则：

- 运行时 `get_prompt()` 只返回最终选中的 Prompt 文本。
- 同一个 Prompt 按 `version desc` 取最新启用版本。
- 指定意图没有 Prompt 时，回退到领域配置的 `fallback_intent`。
- `build_intent_recognition_prompt()` 只负责意图识别 Prompt，不负责每个意图下的 chat Prompt。

### `SeedService`

负责把领域包导入数据库。

领域包包括：

- `automotive.yaml`
- `automotive/prompts/*.txt`

导入后会写入：

- `domain_config`
- `intent_config`
- `prompt_template`

这里使用 `flush()` 而不是 `commit()`，是为了把事务边界交给调用方。以后 CLI、Admin API 或任务队列可以自行决定 commit / rollback。

## 3. Prompt 的三类使用场景

### 意图识别 Prompt

数据库标识：

```text
intent_name = "_system_"
prompt_type = "intent_recognition"
```

作用：让大模型判断用户问题属于哪个意图，并抽取实体。

公开仓库中的汽车领域使用可提交的示例 Prompt：

```text
intent-recognition-new-prompt.txt
```

本地学习时可以替换为已购买 Java 项目中的高质量完整 Prompt，但不要把闭源付费内容提交到公开仓库。

### 业务意图 Chat Prompt

数据库标识：

```text
intent_name = "售前咨询与购买"
prompt_type = "chat"
```

作用：识别出具体业务意图后，用该意图的 Prompt 结合检索上下文生成答案。

例如：

- 售前咨询与购买 -> `car-before-sales-query-prompt.txt`
- 售后维修与保养 -> `car-maintenance-query-prompt.txt`
- 投诉与维权 -> `car-complaints-query-prompt.txt`

### 闲聊方向 Prompt

原参考项目的意图识别设计中包含“闲聊与通用问答”。

Python 版设计上不把闲聊作为 RAG 业务意图，而是未来在 LangGraph 中作为 common chat 分支：

```text
related = false
或 intent = 闲聊与通用问答
  -> common_chat_node
  -> 不走知识库检索
```

后续可以补：

```text
intent_name = "_system_"
prompt_type = "common_chat"
```

## 4. “动态”的两层含义

### 配置动态

这是当前最核心的动态能力。

Prompt 不再写死在代码里，而是来自数据库：

```text
domain_id + intent_name + prompt_type + version
```

这样 Admin 后台改配置后，业务代码不用改。

### 模板替换动态

这是扩展能力。

如果 Prompt 内容是完整文本，就原样返回。

如果 Prompt 内容包含占位符：

```text
{{domain_name}}
{{domain_description}}
{{intent_taxonomy}}
{{entity_schema}}
```

则由 `PromptService` 根据数据库配置进行替换。

当前没有引入 Jinja2，只用轻量 `str.replace()`，原因是 Day 3 主要目标是配置闭环。后续 Day 6 / Day 7 如果 LangGraph 的生成、改写、评分 Prompt 变复杂，再升级为独立 `PromptRenderer` 或 Jinja2。

## 5. FastAPI Admin API 调用链

### Domain API

```text
GET /admin/domains
GET /admin/domains/{domain_id}
```

调用链：

```text
admin_domain_router
  -> Depends(get_db)
  -> DomainConfigService
  -> DomainResponse
```

### Intent API

```text
GET /admin/domains/{domain_id}/intents
```

调用链：

```text
admin_intent_router
  -> Depends(get_db)
  -> DomainConfigService.list_intents_by_domain()
  -> IntentResponse
```

### Prompt API

```text
GET /admin/domains/{domain_id}/prompts?intent_name=售前咨询与购买
```

调用链：

```text
admin_prompt_router
  -> Depends(get_db)
  -> PromptService.list_prompt_templates()
  -> PromptTemplateResponse
```

## 6. Python / FastAPI 关键语法

### `APIRouter`

```python
router = APIRouter(prefix="/admin/domains", tags=["admin-domains"])
```

用于把一组相关接口放在同一个路由模块里，类似 Java 的 `@RestController`。

### `Depends(get_db)`

```python
db: AsyncSession = Depends(get_db)
```

FastAPI 依赖注入。这里用来给接口函数注入数据库 session。

### Pydantic `from_attributes`

```python
model_config = ConfigDict(from_attributes=True)
```

允许 Pydantic 直接从 SQLAlchemy ORM 对象读取字段并输出 JSON。

### SQLAlchemy 动态查询

```python
stmt = select(PromptTemplateModel).where(PromptTemplateModel.domain_id == domain_id)

if intent_name is not None:
    stmt = stmt.where(PromptTemplateModel.intent_name == intent_name)
```

这种写法适合处理可选查询条件，类似 Java 里动态拼 QueryWrapper。

## 7. 验证命令

```bash
uv run pytest know_engine_py/tests/test_seed_service.py -q
uv run pytest know_engine_py/tests/test_prompt_service.py -q
uv run pytest know_engine_py/tests/test_admin_domain_api.py -q
uv run pytest know_engine_py/tests/test_admin_intent_api.py -q
uv run pytest know_engine_py/tests/test_admin_prompt_api.py -q
uv run pytest know_engine_py/tests/test_prompt_dynamic_building.py -q
uv run pytest know_engine_py/tests -q
```

当前全量结果：

```text
26 passed
```

## 8. 面试可讲点

- 我把 Java 项目中写死的领域、意图和 Prompt 抽成数据库配置，形成 `domain_config`、`intent_config`、`prompt_template` 三层动态配置模型。
- Prompt 服务支持按领域、意图、类型和版本选择最新启用模板，并提供 fallback 意图兜底，避免业务意图缺配置导致链路中断。
- 我设计了领域包导入机制，通过 YAML 和 prompt txt 初始化一个行业配置，同时后续可通过 Admin API 查询和维护配置。
- 对于 Prompt 动态化，我区分了“配置动态”和“模板替换动态”：当前公开示例支持占位符渲染，本地也可兼容完整 Prompt；未来可用 Jinja2 扩展为多领域通用模板。
- Admin API 使用 FastAPI Router、Depends 和 Pydantic schema 分层实现，对应 Java/Spring 中的 Controller、Service、Entity、DTO/VO。
