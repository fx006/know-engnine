# Know-Engine 详细实施蓝图（下）Phase 4-6

> 接续上册，覆盖 LangGraph 状态机、SSE 聊天接口、测试部署

---

## Phase 4：LangGraph 状态机（Week 7-8）

### Task 4.1 AgentState 定义 (`app/rag/state.py`)

```python
from typing import TypedDict

class AgentState(TypedDict):
    # 输入
    query: str
    user_id: str
    conversation_id: str
    message_id: str           # 用户消息ID
    assistant_msg_id: str     # assistant消息ID（先创建空记录）
    # 意图识别
    intent_result: dict | None    # {"intent":"售前咨询","entities":{...},"reasoning":"..."}
    is_related: bool
    # 查询处理
    transformed_query: str | None
    # 路由
    route_strategy: str | None    # hybrid / sql / graph
    data_sources: list[str]       # ["milvus","es"] / ["mysql"] / ["neo4j"]
    # 检索
    retrieved_docs: list          # 检索结果
    reranked_docs: list           # 重排后
    graded_docs: list             # 评分通过的
    docs_relevant: bool
    retry_count: int              # Corrective RAG 循环计数
    # 生成
    system_prompt: str | None
    response: str | None
    # 进度消息（SSE推送用）
    progress_messages: list[str]
    # RAG引用溯源
    rag_references: list[dict]
```

### Task 4.2 意图识别节点 (`app/rag/nodes/intent_node.py`)

参考 `IntentRecognitionService.java` + `intent-recognition-new-prompt.txt`(177行)。

```python
async def intent_node(state: AgentState) -> AgentState:
    # 1. 从DB动态构建意图识别Prompt（替代177行硬编码txt）
    system_prompt = await prompt_service.build_intent_recognition_prompt()
    # build_intent_recognition_prompt() 内部：
    #   base_prompt(从DB读) + 意图列表(从intent_config表动态拼) + 实体指令(从entity_schema动态拼)

    # 2. 调用LLM
    result = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["query"])
    ])

    # 3. 解析返回JSON（用json_fixer修复格式）
    parsed = json.loads(json_fixer.fix(result.content))
    # parsed 格式：{"related":true,"intent":"售前咨询与购买","reasoning":"...","entities":{"car_model":"Model 3"}}

    # 4. entities 是动态字典（替代原版7个固定字段）
    state["is_related"] = parsed.get("related", False)
    state["intent_result"] = parsed
    state["progress_messages"] = ["[PROGRESS]:正在识别您的意图..."]
    return state
```

### Task 4.3 查询改写节点 (`app/rag/nodes/transform_node.py`)

参考最新 `KnowEngineQueryTransformer.java`(182行)。

```python
async def transform_node(state: AgentState) -> AgentState:
    # 1. 从DB读取改写Prompt（替代L86-121的硬编码汽车Prompt）
    transform_prompt = await prompt_service.get_prompt("_system_", "query_transform")

    # 2. LLM改写
    result = await llm.ainvoke([
        SystemMessage(content=transform_prompt),
        HumanMessage(content=state["query"])
    ])
    rewritten = result.content.strip()

    # 3. 拼接增强查询（保留Java版的格式：L150）
    enhanced = f"我的问题是：{rewritten}, 我的用户Id是: {state['user_id']}, 现在是：{datetime.now()}"
    state["transformed_query"] = enhanced

    # 4. 异步回写改写结果到chat_message.transform_content（参考Java L161-169虚拟线程）
    asyncio.create_task(
        msg_service.update_transform_content(state["message_id"], enhanced)
    )

    state["progress_messages"].append("[PROGRESS]:正在优化您的问题...")
    return state
```

### Task 4.4 路由决策节点 (`app/rag/nodes/router_node.py`)

**关键改造**：Java版用LLM判断路由（`KnowEngineQueryRouter` L68-104 内嵌Prompt），改造后**直接从DB读取**。

```python
async def router_node(state: AgentState) -> AgentState:
    intent_name = state["intent_result"]["intent"]

    # 直接从DB intent_config表读取该意图的检索策略（不再调LLM）
    intent_cfg = await config_service.get_intent_config(intent_name)

    state["route_strategy"] = intent_cfg.retrieval_strategy    # "hybrid" / "sql" / "graph"
    state["data_sources"] = json.loads(intent_cfg.data_sources) # ["milvus","es"]
    return state
```

### Task 4.5 多源检索节点 (`app/rag/nodes/retriever_node.py`)

参考 `ChatApplicationService.java` L117-146 的4路检索器构建。

```python
async def retriever_node(state: AgentState) -> AgentState:
    query = state["transformed_query"] or state["query"]
    strategy = state["route_strategy"]

    # 根据策略分发（参考ProgressAwareContentRetriever的进度推送）
    if strategy == "hybrid":
        state["progress_messages"].append("[PROGRESS]:正在检索知识库内容...")
        docs = await hybrid_retriever.ainvoke(query)
    elif strategy == "sql":
        state["progress_messages"].append("[PROGRESS]:正在检索数据库内容...")
        docs = await sql_retriever.ainvoke(query)
    elif strategy == "graph":
        state["progress_messages"].append("[PROGRESS]:正在检索图数据库内容...")
        docs = await neo4j_retriever.ainvoke(query)
    else:
        docs = await hybrid_retriever.ainvoke(query)

    state["retrieved_docs"] = docs
    return state
```

### Task 4.6 重排序 + RAG引用溯源节点 (`app/rag/nodes/reranker_node.py`)

**合并** BGE重排 + `ProgressAwareContentAggregator.java`(101行L62-86)的引用溯源：

```python
async def reranker_node(state: AgentState) -> AgentState:
    state["progress_messages"].append("[PROGRESS]:正在排序筛选结果...")

    # 1. BGE 重排序
    query = state["transformed_query"] or state["query"]
    pairs = [(query, doc.page_content) for doc in state["retrieved_docs"]]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(state["retrieved_docs"], scores), key=lambda x: x[1], reverse=True)
    state["reranked_docs"] = [doc for doc, _ in ranked[:5]]

    # 2. 提取RAG引用溯源（参考ProgressAwareContentAggregator L62-86）
    rag_refs = []
    seen_doc_ids = set()
    for doc, score in ranked[:5]:
        doc_id = doc.metadata.get(MetadataKey.DOC_ID)
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        rag_refs.append({
            "documentId": str(doc_id),
            "chunkId": doc.metadata.get(MetadataKey.CHUNK_ID),
            "url": doc.metadata.get(MetadataKey.URL),
            "documentTitle": doc.metadata.get(MetadataKey.FILE_NAME),
            "chunkContent": doc.page_content[:200],
            "rerankScore": float(score)
        })
    state["rag_references"] = rag_refs

    # 3. 回写rag_references到DB（参考Java L79-81）
    if rag_refs and state.get("assistant_msg_id"):
        asyncio.create_task(
            msg_service.update_rag_references(state["assistant_msg_id"], rag_refs)
        )
    # 4. 推送[REFERENCE]事件（参考Java L84）
    state["progress_messages"].append(f"[REFERENCE]:{json.dumps(rag_refs, ensure_ascii=False)}")
    return state
```

### Task 4.7 质量评分节点 — Corrective RAG（新增，Java版没有）

```python
async def grader_node(state: AgentState) -> AgentState:
    grader_prompt = await prompt_service.get_prompt("_system_", "grader")
    relevant = []
    for doc in state["reranked_docs"]:
        result = await llm.ainvoke([
            SystemMessage(content=grader_prompt),
            HumanMessage(content=f"问题：{state['query']}\n文档：{doc.page_content[:500]}")
        ])
        if "yes" in result.content.lower():
            relevant.append(doc)

    state["graded_docs"] = relevant
    state["docs_relevant"] = len(relevant) > 0
    state["retry_count"] = state.get("retry_count", 0) + 1
    return state
```

### Task 4.8 查询重写节点（Corrective RAG 循环用）

```python
async def rewrite_node(state: AgentState) -> AgentState:
    state["progress_messages"].append("[PROGRESS]:检索结果不理想，正在重新检索...")
    result = await llm.ainvoke([
        SystemMessage(content="请用不同的措辞重新表述以下问题，以获得更好的搜索结果："),
        HumanMessage(content=state["query"])
    ])
    state["transformed_query"] = result.content.strip()
    return state
```

### Task 4.9 Prompt 选择节点

```python
async def prompt_select_node(state: AgentState) -> AgentState:
    # 从DB读取该意图的聊天Prompt（替代原版从txt文件读取）
    intent_name = state["intent_result"]["intent"]
    prompt = await prompt_service.get_prompt(intent_name, "chat")
    state["system_prompt"] = prompt
    state["progress_messages"].append("[PROGRESS]:正在生成回答...")
    return state
```

### Task 4.10 流式生成节点

参考 `ChatApplicationService.java` L179-192：

```python
async def generator_node(state: AgentState) -> AgentState:
    context = "\n\n".join([doc.page_content for doc in state["graded_docs"]])
    messages = [
        SystemMessage(content=state["system_prompt"]),
        HumanMessage(content=f"参考资料：\n{context}\n\n用户问题：{state['query']}")
    ]
    response = await llm.ainvoke(messages)
    state["response"] = response.content
    return state
```

### Task 4.11 图编排 (`app/rag/graph.py`)

```python
from langgraph.graph import StateGraph, END

def build_rag_graph():
    builder = StateGraph(AgentState)

    builder.add_node("intent", intent_node)
    builder.add_node("common_chat", common_chat_node)
    builder.add_node("transform", transform_node)
    builder.add_node("router", router_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("reranker", reranker_node)
    builder.add_node("grader", grader_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("prompt_select", prompt_select_node)
    builder.add_node("generator", generator_node)

    builder.set_entry_point("intent")

    # 意图分流
    builder.add_conditional_edges("intent", lambda s:
        "common_chat" if not s["is_related"] else "transform")

    # 线性边
    builder.add_edge("transform", "router")
    builder.add_edge("router", "retriever")
    builder.add_edge("retriever", "reranker")
    builder.add_edge("reranker", "grader")

    # Corrective RAG 循环边
    builder.add_conditional_edges("grader", lambda s:
        "rewrite" if not s["docs_relevant"] and s["retry_count"] < 2
        else "prompt_select")
    builder.add_edge("rewrite", "router")  # 回到路由重新检索

    builder.add_edge("prompt_select", "generator")
    builder.add_edge("generator", END)
    builder.add_edge("common_chat", END)

    return builder.compile()
```

---

## Phase 5：聊天与会话（Week 9）

### Task 5.1 会话和消息服务

平移最新 `ChatMessageServiceImpl.java`(110行) 的所有方法：

| 方法 | 用途 | Python 对应 |
|------|------|------------|
| `saveUserMessage()` | 保存用户消息 | `save_user_message(conv_id, content) -> msg_id` |
| `saveAssistantMessage()` | 创建空assistant记录 | `save_assistant_message(conv_id) -> msg_id` |
| `updateContent()` | 回写LLM完整回答 | `update_content(msg_id, content)` |
| `updateTransformContent()` | 回写查询改写结果 | `update_transform_content(msg_id, content)` |
| `updateRagReferences()` | 回写RAG引用溯源JSON | `update_rag_references(msg_id, refs)` |
| `getMessagesByConversationId()` | 消息列表 | `get_messages(conv_id) -> list` |
| `getRecentMessages()` | 最近N条（上下文） | `get_recent_messages(conv_id, limit)` |
| `deleteMessagesByConversationId()` | 删会话下所有消息 | `delete_messages(conv_id)` |

### Task 5.2 标题摘要服务

参考最新 `ChatController.java` L86-104：
- 使用低成本模型（qwen3.5-flash），不用主力模型
- 异步执行，不阻塞首 token
- 用 content[:20] 作临时标题，LLM生成后更新

### Task 5.3 SSE 流式对话接口（最终交付物）

**参考**：最新 `ChatController.java` L70-137 + `ChatApplicationService.java` L101-200。

```python
@router.post("/chat/send")
async def send(userId: str, content: str, conversationId: str = None):
    # 1. 会话处理（参考Java L77-107）
    if not conversationId:
        temp_title = content[:20]
        conv_id = await conv_service.create(userId, temp_title)
        # 异步标题生成（参考Java L86-104虚拟线程）
        asyncio.create_task(generate_title(conv_id, content))
    else:
        conv_id = conversationId

    # 2. 保存消息（参考Java L110-112）
    msg_id = await msg_service.save_user_message(conv_id, content)
    assistant_msg_id = await msg_service.save_assistant_message(conv_id)

    # 3. 构建初始状态
    state = AgentState(
        query=content, user_id=userId, conversation_id=conv_id,
        message_id=msg_id, assistant_msg_id=assistant_msg_id,
        retry_count=0, is_related=False, intent_result=None,
        transformed_query=None, route_strategy=None, data_sources=[],
        retrieved_docs=[], reranked_docs=[], graded_docs=[],
        docs_relevant=False, system_prompt=None, response=None,
        progress_messages=[], rag_references=[]
    )

    # 4. SSE流式返回
    async def stream():
        # 先推送意图识别进度（参考Java L115）
        yield "data: [PROGRESS]:正在识别您的意图...\n\n"

        final_response = ""
        async for event in rag_graph.astream(state, stream_mode="updates"):
            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # 推送该节点产生的进度消息
            for msg in node_output.get("progress_messages", []):
                yield f"data: {msg}\n\n"

            # generator节点的最终回答
            if node_name == "generator" and node_output.get("response"):
                final_response = node_output["response"]
                yield f"data: {final_response}\n\n"

        # 5. 持久化assistant回答（参考Java L191）
        await msg_service.update_content(assistant_msg_id, final_response)

        # 6. 流结束标记（参考Java L136）
        yield f"data: [DONE]:{conv_id}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

**SSE 事件协议**（必须保持一致，前端依赖这些格式）：

| 事件格式 | 含义 | 来源节点 |
|---------|------|---------|
| `[PROGRESS]:正在识别您的意图...` | 意图识别 | ChatController |
| `[PROGRESS]:正在优化您的问题...` | 查询改写 | transform_node |
| `[PROGRESS]:正在检索知识库内容...` | 向量检索 | retriever_node |
| `[PROGRESS]:正在检索数据库内容...` | SQL检索 | retriever_node |
| `[PROGRESS]:正在排序筛选结果...` | 重排序 | reranker_node |
| `[REFERENCE]:[{...}]` | RAG引用溯源 | reranker_node |
| `[PROGRESS]:正在生成回答...` | 开始生成 | prompt_select_node |
| `(LLM tokens)` | 逐token推送 | generator_node |
| `[DONE]:conversationId` | 流结束 | ChatController |

### Task 5.4 会话管理接口

参考最新 `ChatController.java`：
- `GET /chat/list?userId=` — 会话列表
- `GET /chat/messages?conversationId=` — 消息历史
- `DELETE /chat/{conversationId}` — 删除会话+消息

---

## Phase 6：测试与部署（Week 10）

### Task 6.1 分割器单元测试

用 Java `src/test/resources/` 下的 Markdown 文件验证 chunk 数量和 metadata 一致性。

### Task 6.2 Docker Compose

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [mysql, redis, milvus, elasticsearch, minio, neo4j]
  celery-worker:
    build: .
    command: celery -A app.tasks.celery_app worker -l info
  celery-beat:
    build: .
    command: celery -A app.tasks.celery_app beat -l info
  mysql:
    image: mysql:8.0
  redis:
    image: redis:7
  milvus:
    image: milvusdb/milvus:latest
  elasticsearch:
    image: elasticsearch:8.15.0
  minio:
    image: minio/minio
  neo4j:
    image: neo4j:5
```

### Task 6.3 端到端验证

| # | 验证项 | 预期结果 |
|---|--------|---------|
| 1 | `GET /api/admin/domain` | 返回汽车领域预设配置 |
| 2 | `GET /api/admin/intents` | 返回6个汽车意图 |
| 3 | 上传 PDF → convert → split | Milvus 和 ES 中有数据 |
| 4 | `POST /chat/send` "发动机异响怎么处理" | SSE流式返回：PROGRESS×5 → REFERENCE → tokens → DONE |
| 5 | `POST /chat/send` "今天天气怎么样" | is_related=false，走通用对话 |
| 6 | 检查 chat_message 表 | content已回写、transform_content已回写、rag_references已回写 |
| 7 | 新增意图 → 重新调意图识别 | 新意图被识别 |
| 8 | 修改Prompt → 重新对话 | 新Prompt立即生效 |

---

## 完整执行顺序

```
Phase 1 (W1-2): 1.1→1.2→1.3→1.4→1.5→1.6→1.7→1.8→1.9→1.10→1.10b→1.11→1.12
Phase 2 (W3-4): 2.1→2.2→2.3→2.4→2.5→2.6→2.7→2.8→2.9→2.10
Phase 3 (W5-6): 3.1→3.2→3.3→3.4→3.5→3.6
Phase 4 (W7-8): 4.1→4.2→4.3→4.4→4.5→4.6→4.7→4.8→4.9→4.10→4.11
Phase 5 (W9):   5.1→5.2→5.3→5.4
Phase 6 (W10):  6.1→6.2→6.3
共 45+ Task
```
