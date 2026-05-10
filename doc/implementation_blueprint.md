# Know-Engine 详细实施蓝图（上）Phase 1-3

> **版本基线**：`langchain==1.2.x` | `langgraph==1.1.x` | `Python>=3.10`
> **Java 参考**：`know-engine/src/main/java/cn/hollis/llm/mentor/know/engine/`

---

## Phase 1：基础骨架 + 动态配置（Week 1-2）

### Task 1.1 项目初始化

创建项目，配置 pyproject.toml：

```toml
[project]
name = "know-engine-py"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi[standard]>=0.115",
    "sqlalchemy[asyncio]>=2.0", "asyncmy>=0.2", "alembic>=1.14",
    "langchain>=1.2", "langchain-openai>=0.3", "langgraph>=1.1",
    "langchain-milvus>=0.2", "pymilvus>=2.5",
    "elasticsearch[async]>=8.0", "langchain-neo4j>=0.2",
    "sentence-transformers>=3.0",
    "minio>=7.0", "redis>=5.0", "celery[redis]>=5.4",
    "httpx>=0.27", "openpyxl>=3.1", "pydantic-settings>=2.0", "pyyaml>=6.0",
]
```

### Task 1.2 配置管理 (`config/settings.py`)

参考 Java `application.yml`，用 pydantic-settings 实现所有外部服务连接配置（DB/Redis/Milvus/ES/Neo4j/MinIO/MinerU/LLM/Embedding/领域ID）。

### Task 1.3 枚举定义 (`app/models/enums.py`)

平移 Java `constant/` 目录：`DocumentStatus`(6态)、`FileType`(4种)、`SplitType`(5种)、`SegmentStatus`、`ChatMessageType`(USER/ASSISTANT)。新增 `RetrievalSource`(knowledge_base/relational_db/graph_db)。

### Task 1.4 ORM 基类 (`app/models/base.py`)

SQLAlchemy 2.0 DeclarativeBase + BaseEntity（id/created_at/updated_at）。

### Task 1.5 ORM 模型 — 8张表

**5张保留表**参考最新 `tables.sql`（107行）和 Java entity 类：

- `knowledge_document` — 注意 `extension` 是 JSON（存重试次数）、`lock_version` 乐观锁
- `knowledge_segment` — 注意 `metadata_` 是 JSON、`skip_embedding` 布尔
- `table_meta` — `columns_info` 是 JSON
- `chat_conversation` — conversation_id 唯一索引
- `chat_message` — **新增** `rag_references` JSON 字段（`81ed40c` 提交新增）

**3张新增配置表**的 ORM 定义：

```python
# models/domain_config.py
class DomainConfigModel(BaseEntity):
    __tablename__ = "domain_config"
    domain_id = mapped_column(String(64), unique=True, nullable=False)
    name = mapped_column(String(128), nullable=False)
    description = mapped_column(String(512))
    is_active = mapped_column(SmallInteger, default=1)
    fallback_intent = mapped_column(String(128), default="其他")
    entity_schema = mapped_column(JSON, comment='动态实体字段定义')
    # entity_schema 示例：{"car_model":"汽车型号","dealer":"4S店名称",...}

# models/intent_config.py
class IntentConfigModel(BaseEntity):
    __tablename__ = "intent_config"
    domain_id = mapped_column(String(64), nullable=False)
    intent_name = mapped_column(String(128), nullable=False)
    intent_description = mapped_column(String(512))
    retrieval_strategy = mapped_column(String(32), default="hybrid")
    data_sources = mapped_column(String(256), default='["milvus","es"]')
    sort_order = mapped_column(Integer, default=0)
    is_active = mapped_column(SmallInteger, default=1)

# models/prompt_template.py
class PromptTemplateModel(BaseEntity):
    __tablename__ = "prompt_template"
    domain_id = mapped_column(String(64), nullable=False)
    intent_name = mapped_column(String(128), nullable=False)  # '_system_' 表示系统级
    prompt_type = mapped_column(String(32), nullable=False)
    # prompt_type 取值：intent_recognition / query_route / query_transform / grader / chat / general_chat
    content = mapped_column(Text, nullable=False)
    version = mapped_column(Integer, default=1)
    is_active = mapped_column(SmallInteger, default=1)
```

### Task 1.6-1.7 FastAPI 入口 + 依赖注入

lifespan 中调用种子初始化。deps.py 提供 get_db/get_redis/get_milvus/get_es。

### Task 1.8 工具类平移

`SnowflakeIdGenerator` / `JsonUtil`（修复LLM输出JSON） / `FileTypeUtil`。

### Task 1.9 Metadata 常量

平移 `MetadataKeyConstant.java` 的15个常量（FILE_NAME/DOC_ID/CHUNK_ID/PARENT_CHUNK_ID/BROTHER_CHUNK_ID/BROTHER_CHUNK_INDEX/BROTHER_CHUNK_TOTAL/...），保持 camelCase 命名。

### Task 1.10 领域配置服务（核心改造 — 动态可配置的关键）

**`app/services/domain_config.py`**：

```python
class DomainConfigService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache_ttl = 300  # 5分钟缓存

    async def get_domain(self) -> DomainConfigModel:
        """获取当前激活的领域配置（Redis缓存）"""
        cache_key = "domain:config"
        cached = await self.redis.get(cache_key)
        if cached:
            return DomainConfigModel.parse_raw(cached)
        domain = (await self.db.execute(
            select(DomainConfigModel).where(DomainConfigModel.is_active == 1)
        )).scalar_one()
        await self.redis.setex(cache_key, self.cache_ttl, domain.json())
        return domain

    async def get_intents(self, domain_id: str) -> list[IntentConfigModel]:
        """获取领域下所有激活意图（Redis缓存）"""
        cache_key = f"domain:{domain_id}:intents"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        result = (await self.db.execute(
            select(IntentConfigModel)
            .where(IntentConfigModel.domain_id == domain_id)
            .where(IntentConfigModel.is_active == 1)
            .order_by(IntentConfigModel.sort_order)
        )).scalars().all()
        await self.redis.setex(cache_key, self.cache_ttl, json.dumps([i.dict() for i in result]))
        return result

    async def get_intent_config(self, intent_name: str) -> IntentConfigModel | None:
        """通过意图名查找配置 — 替代原版 KnowEngineIntent.getIntent() 的 switch-case"""
        domain = await self.get_domain()
        intents = await self.get_intents(domain.domain_id)
        for intent in intents:
            if intent.intent_name == intent_name:
                return intent
        # fallback 到默认意图 — 替代原版 default -> CAR_OTHER_QUERY
        return await self.get_intent_config(domain.fallback_intent)

    async def invalidate_cache(self, domain_id: str):
        """前端修改配置后调用 — 清除缓存使新配置立即生效"""
        keys = await self.redis.keys(f"domain:{domain_id}:*")
        if keys:
            await self.redis.delete(*keys)
        await self.redis.delete("domain:config")

    async def seed_from_yaml(self, yaml_path: str = "config/domains/automotive.yaml"):
        """首次启动时将YAML种子数据导入DB"""
        existing = (await self.db.execute(select(DomainConfigModel).limit(1))).scalar()
        if existing:
            return  # 已有数据，不重复导入
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        # 写入领域配置
        self.db.add(DomainConfigModel(domain_id=config["domain"]["id"], ...))
        # 写入意图配置
        for intent in config["intents"]:
            self.db.add(IntentConfigModel(**intent))
        # 写入Prompt模板（从 prompts/ 目录读取txt文件内容）
        for prompt_file in config["prompts"]:
            content = Path(f"prompts/{config['domain']['id']}/{prompt_file['file']}").read_text()
            self.db.add(PromptTemplateModel(
                domain_id=config["domain"]["id"],
                intent_name=prompt_file["intent_name"],
                prompt_type=prompt_file["type"],
                content=content
            ))
        await self.db.commit()
```

### Task 1.10b Prompt 服务（核心改造 — 意图识别Prompt自动拼装）

**`app/services/prompt_service.py`**：

```python
class PromptService:
    def __init__(self, config_service: DomainConfigService, db: AsyncSession, redis: Redis):
        self.config_service = config_service
        self.db = db
        self.redis = redis

    async def get_prompt(self, intent_name: str, prompt_type: str) -> str:
        """从DB读取Prompt（带Redis缓存 + fallback）— 替代原版 PromptService.loadPromptFromFile()"""
        domain = await self.config_service.get_domain()
        cache_key = f"prompt:{domain.domain_id}:{intent_name}:{prompt_type}"
        cached = await self.redis.get(cache_key)
        if cached:
            return cached.decode()
        result = (await self.db.execute(
            select(PromptTemplateModel)
            .where(PromptTemplateModel.domain_id == domain.domain_id)
            .where(PromptTemplateModel.intent_name == intent_name)
            .where(PromptTemplateModel.prompt_type == prompt_type)
            .where(PromptTemplateModel.is_active == 1)
            .order_by(PromptTemplateModel.version.desc())
            .limit(1)
        )).scalar_one_or_none()
        if result is None:
            # fallback — 替代原版的 if(intent != CAR_OTHER_QUERY) return getPrompt(CAR_OTHER_QUERY)
            return await self.get_prompt(domain.fallback_intent, prompt_type)
        await self.redis.setex(cache_key, 300, result.content)
        return result.content

    async def build_intent_recognition_prompt(self) -> str:
        """动态拼装意图识别Prompt — 替代原版 intent-recognition-new-prompt.txt(177行)"""
        domain = await self.config_service.get_domain()
        intents = await self.config_service.get_intents(domain.domain_id)

        # 1. 基础角色描述（从DB读取，可在线编辑）
        base = await self.get_prompt("_system_", "intent_recognition")

        # 2. 动态拼接意图列表（从intent_config表生成，新增意图自动出现）
        intent_list = "\n## 意图类别\n"
        for i, intent in enumerate(intents, 1):
            intent_list += f"{i}. **{intent.intent_name}**\n"
            if intent.intent_description:
                intent_list += f"   - {intent.intent_description}\n"

        # 3. 动态拼接实体提取指令（从domain_config.entity_schema生成）
        entity_section = ""
        if domain.entity_schema:
            entity_section = "\n## 实体提取\n从用户输入中提取以下实体信息：\n"
            for field, desc in domain.entity_schema.items():
                entity_section += f"- {field}: {desc}\n"

        return base + intent_list + entity_section
```

### Task 1.11 领域管理 API（9个接口）

**`app/api/admin_router.py`**：

```python
router = APIRouter(prefix="/api/admin", tags=["领域管理"])

# 领域
GET    /api/admin/domain                    # 获取当前领域配置
PUT    /api/admin/domain                    # 更新领域配置

# 意图
GET    /api/admin/intents                   # 获取所有意图列表
POST   /api/admin/intents                   # 新增意图
PUT    /api/admin/intents/{intent_name}     # 修改意图（检索策略、数据源等）
DELETE /api/admin/intents/{intent_name}     # 删除意图

# Prompt
GET    /api/admin/prompts                   # 获取Prompt列表（支持按意图筛选）
POST   /api/admin/prompts                   # 新增Prompt
PUT    /api/admin/prompts/{id}              # 编辑Prompt内容（version自增）
```

**关键**：每个写操作末尾必须调用 `await config_service.invalidate_cache(domain_id)`。

### Task 1.12 Alembic 初始化 + 种子数据 YAML

---

## Phase 2：文档处理管线（Week 3-4）

### Task 2.1 文件存储 (`app/services/file_storage.py`)

封装 MinIO SDK：upload_file / get_file_url / delete_file。参考 `FileStorageService.java`。

### Task 2.2 MinerU 在线 API 客户端

**重写** `MinerUProcessBaseServiceImpl.java`(572行) → 调用官方在线API。提交解析任务→轮询结果→返回 Markdown+图片列表。零GPU运维。

### Task 2.3-2.5 文件处理器

工厂模式 + PDF/Word/Excel 处理器。参考 `FileProcessServiceFactory.java` 和各 Impl。Excel 需注意键值对/表格双模式（参考 `ExcelProcessServiceImpl.java` 447行）。

### Task 2.6 三个文档分割器（最核心的平移）

**为什么这是最重要的 Task**：分割器产生的 metadata 关系（parentChunkId/brotherChunkId/brotherChunkIndex 等）直接决定检索时的上下文扩展质量。

| Java 源文件 | 行数 | 平移要点 |
|------------|------|---------|
| `MarkdownHeaderParentTextSplitter.java` | ~500 | 标题栈管理；父chunk `skipEmbedding=true`；子chunk 包含 `parentChunkId` |
| `MarkdownHeaderBrotherTextSplitter.java` | ~500 | 同标题层级 chunk 共享 `brotherChunkId`；记录 index 和 total |
| `ExcelSplitter.java` | ~100 | 键值对/HTML表格双模式 |

分割器工厂根据 SplitType 枚举返回对应分割器（参考 `DocumentSplitterFactory.java`）。

### Task 2.7 文档处理编排 (`app/services/document_process.py`)

参考 `DocumentProcessServiceImpl.java`，四阶段：
1. `upload()` → MinIO + DB，状态 UPLOADED
2. `convert()` → FileProcessor，状态 CONVERTED
3. `split()` → SplitterFactory，保存 segments，状态 CHUNKED
4. `embed_and_store()` → **双写**：
   - skipEmbedding=false → embedding → Milvus
   - 所有 segments → 原文+metadata → ES
   - 更新状态 VECTOR_STORED

### Task 2.8-2.9 Celery 任务 + 补偿

替代 Spring Event + XXL-Job。split() 完成后 dispatch Celery task 执行 embed_and_store()。补偿任务用 Celery Beat 定时扫描。参考 `DocumentCompensationJob.java`(191行)。

### Task 2.10 文档管理 API

7个接口：upload/list/detail/convert/split/delete + 分段列表。

---

## Phase 3：检索引擎（Week 5-6）

### Task 3.1 Milvus 向量检索器（带上下文扩展）

参考 `KnowEngineElasticsearchContentRetriever.java`(281行) 的 expandContext() 逻辑：

```python
class MilvusRetrieverWithExpansion(BaseRetriever):
    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        # 1. Milvus ANN 语义检索（只检索 skipEmbedding!=true 的子chunk）
        hits = await self.milvus.asimilarity_search(query, k=self.top_k)

        # 2. 上下文扩展
        expanded = []
        for doc in hits:
            parent_id = doc.metadata.get(MetadataKey.PARENT_CHUNK_ID)
            if parent_id:
                # 通过 parentChunkId 从 ES 获取父chunk完整内容（替换子chunk片段）
                parent = await self.es.get(index=self.index, id=parent_id)
                doc.page_content = parent["_source"]["content"]

            brother_id = doc.metadata.get(MetadataKey.BROTHER_CHUNK_ID)
            if brother_id:
                # 通过 brotherChunkId 从 ES 获取同级所有兄弟chunk（补充上下文）
                brothers = await self.es.search(
                    index=self.index,
                    query={"term": {MetadataKey.BROTHER_CHUNK_ID: brother_id}},
                    sort=[{MetadataKey.BROTHER_CHUNK_INDEX: "asc"}]
                )
                for b in brothers["hits"]["hits"]:
                    expanded.append(Document(page_content=b["_source"]["content"], metadata=b["_source"]))
            expanded.append(doc)
        return deduplicate_by_chunk_id(expanded)
```

### Task 3.2 ES 关键词检索器

ES 仅做 BM25，使用 ik_smart 分词器：

```python
class ESKeywordRetriever(BaseRetriever):
    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        result = await self.es.search(
            index=self.index,
            query={"match": {"content": {"query": query, "analyzer": "ik_smart"}}},
            size=self.top_k
        )
        return [Document(page_content=h["_source"]["content"], metadata=h["_source"])
                for h in result["hits"]["hits"]]
```

### Task 3.3 混合检索器（RRF 融合）

并发 Milvus + ES，RRF(k=60) 融合排序：

```python
class HybridRetriever(BaseRetriever):
    async def _aget_relevant_documents(self, query: str) -> list[Document]:
        vec_results, kw_results = await asyncio.gather(
            self.milvus_retriever.ainvoke(query),
            self.es_retriever.ainvoke(query)
        )
        # RRF: score(d) = Σ 1/(k + rank_i)
        scores, doc_map = {}, {}
        for rank, doc in enumerate(vec_results):
            cid = doc.metadata[MetadataKey.CHUNK_ID]
            scores[cid] = scores.get(cid, 0) + 1 / (rank + 60)
            doc_map[cid] = doc
        for rank, doc in enumerate(kw_results):
            cid = doc.metadata[MetadataKey.CHUNK_ID]
            scores[cid] = scores.get(cid, 0) + 1 / (rank + 60)
            doc_map[cid] = doc
        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:self.top_n]
        return [doc_map[cid] for cid in sorted_ids]
```

### Task 3.4 SQL 检索器

参考 `ChatApplicationService.java` L134-138。注意 Java 版 SQL 检索器的 promptTemplate 和 databaseStructure 是硬编码占位符（TODO），Python 版需正式实现 Text2SQL。

### Task 3.5 Neo4j 图谱检索器

参考 `ChatApplicationService.java` L141-146。使用 `langchain-neo4j`。

### Task 3.6 BGE 重排序器

替代 `BgeScoringModel.java`(ONNX) → Python `sentence-transformers` CrossEncoder：

```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)

async def reranker_node(state: AgentState) -> AgentState:
    query = state["transformed_query"] or state["query"]
    pairs = [(query, doc.page_content) for doc in state["retrieved_docs"]]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(state["retrieved_docs"], scores), key=lambda x: x[1], reverse=True)
    state["reranked_docs"] = [doc for doc, _ in ranked[:5]]
    return state
```
