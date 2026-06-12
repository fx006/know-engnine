# Chat SSE Protocol

本文档定义 `/chat/send` 的 SSE 输出契约。它面向前端、联调脚本和后续真实流式改造。

当前实现处于两层状态：

- 协议层：事件格式稳定，前端可以按本文档解析。
- 图执行层：已接入 `graph.astream(..., stream_mode=["updates","custom"])`；`updates` 输出节点级 progress，`custom` 输出 generator 写出的 answer_delta。如果注入的 graph 不支持 `astream`，会 fallback 到完整结果包装。
- 生成层：generator 会优先消费模型 `astream()` 并输出 answer_delta；如果模型/provider 只返回整段文本，则仍会表现为单次或较粗粒度 delta。

## Transport

Endpoint:

```text
POST /chat/send
```

Response content type:

```text
text/event-stream
```

当前采用 Java 兼容的 data-only frame，不使用 `event:` 字段：

```text
data: <payload>

```

多行答案会被拆成多个 `data:` 行：

```text
data: 第一行
data: 第二行

```

## Event Payloads

### progress

用途：展示后端处理进度。

Wire format:

```text
data: [PROGRESS]:正在识别您的意图...

```

### answer_delta

用途：输出答案增量。

Wire format:

```text
data: Model 3 建议按官方手册周期保养。

```

注意：为了兼容 Java 版，答案文本本身不带 `[ANSWER]` 前缀。前端可把没有业务前缀的 data 视为 `answer_delta`。

当前边界：后端已接入 generator custom stream；实际粒度取决于模型 provider 的 `astream()` 输出，可能是 token，也可能是较粗的文本 chunk。

### reference

用途：输出 RAG 引用。

Wire format:

```text
data: [REFERENCE]:[{"chunkId":"chunk-1","documentTitle":"保养手册"}]

```

引用可以是文档 chunk，也可以是 Text-to-SQL 结构化引用。前端应优先根据 `sourceType` / `retrievalSource` 区分展示。

### card

用途：输出澄清卡片，例如让用户先选择车辆。

Wire format:

```text
data: [CARD]:请先选择车辆

```

### card_choice

用途：输出卡片选项。

Wire format:

```text
data: [CARD_CHOICE_MYCAR]:[{"carId":"car-1","displayName":"Model Y"}]

```

当前已知类型：

- `[CARD_CHOICE_MYCAR]`
- `[CARD_CHOICE_CAR]`

持久化约定：

- `reference` 会写入 assistant 消息的 `rag_references`。
- `card` / `card_choice` 会写入 assistant 消息的 `extra_metadata.clarificationEvents`。
- 前端如果刷新消息列表，应优先根据 `extra_metadata.clarificationEvents` 还原澄清卡片，而不是只依赖当次 SSE 流。

### warning

用途：输出非致命警告，例如证据不足、无可选车辆、弱证据提示。

后端正式来源：

- `AgentState.warning_messages`
- `AgentState.evidence_warning`

`progress_messages` 中历史遗留的 `[WARN]:...` 只作为短期兼容，不是推荐写入位置。

Wire format:

```text
data: [WARN]:当前检索证据不足，已停止生成回答。

```

### error

用途：输出图执行过程中产生的业务错误。

Wire format:

```text
data: [ERROR]:{"code":"GRAPH_ERROR","message":"检索服务暂时不可用"}

```

说明：

- 参数校验错误仍使用 HTTP 4xx，例如空消息内容。
- 当前已完成图内 `state.error` 到 `[ERROR]` 的映射。
- 流式执行中，StreamingResponse 已经开始后发生的运行时异常，也会转换为 `[ERROR]`，避免前端看到空白断流。

### done

用途：标记本轮会话输出结束。

Wire format:

```text
data: [DONE]:<conversationId>

```

前端收到 `[DONE]` 后可以停止 loading，并用 conversationId 关联后续消息列表刷新。

## Recommended Client Parsing

前端解析建议：

1. 去掉每个 SSE frame 的 `data: ` 前缀。
2. 如果 payload 以 `[PROGRESS]:` 开头，作为 progress。
3. 如果 payload 以 `[REFERENCE]:` 开头，解析后面的 JSON。
4. 如果 payload 以 `[CARD]:` 开头，展示卡片文案。
5. 如果 payload 以 `[CARD_CHOICE_` 开头，解析后面的 JSON 选项。
6. 如果 payload 以 `[WARN]:` 开头，展示 warning。
7. 如果 payload 以 `[ERROR]:` 开头，解析错误 JSON。
8. 如果 payload 以 `[DONE]:` 开头，结束本轮流。
9. 其他 payload 均作为 answer_delta 追加到答案区域。

## Current Limitations

- 当前 `/chat/send` 已优先消费 `graph.astream(..., stream_mode=["updates","custom"])`，可以更早输出节点级 progress 和 generator answer_delta；不支持 `astream` 的测试图或旧图会回退到完整结果包装。
- 当前 answer_delta 粒度取决于模型/provider 的 streaming 能力；如果 provider 只返回整段文本，前端仍只会看到一次完整 delta。
- 当前 progress 来自 LangGraph 节点更新中的 `progress_messages`，不是模型 token 回调。
- warning 已有独立的 `warning_messages` 语义字段；不要把新的 warning 写入 `progress_messages`。
- 流中异常会输出 `[ERROR]`，但异常后不会继续输出 `[DONE]`。
- assistant 消息在图执行完成后统一回写；流式 delta 只用于前端实时展示，最终持久化仍以聚合后的 `response` 为准。

## Future Work

- 继续用真实模型和浏览器联调 answer_delta 粒度与断线行为。
- 对 weak evidence 输出 `[WARN]`，并继续生成谨慎回答。
- 前端展示引用卡片、SQL 结果卡片和澄清卡片。
