# Know Engine Web

Know Engine 的前端控制台，当前定位是 v0.1 演示和联调入口。

它不是一个独立的纯前端 demo，而是直接连接本地 FastAPI 后端，消费真实认证、知识库、文档、Chat SSE、健康检查等接口。

## 功能范围

当前已经接入：

- 登录：调用 `/auth/login` 和 `/auth/me` 获取当前用户。
- 知识库选择：调用 `/knowledge-bases` 加载当前用户可访问知识库。
- 对话工作台：调用 `/chat/send`，消费后端 SSE 事件。
- 最近会话：调用 `/chat/list` 和 `/chat/messages` 还原历史消息、引用和澄清卡片。
- 文档工作台：调用 `/documents`、`/documents/import`、`/documents/{id}/split`、`/documents/{id}/segments`、`/documents/{id}/tasks`。
- 环境健康中心：调用 `/health?deep=true` 展示后端和中间件状态。
- 引用展示：普通文档引用和 Text-to-SQL 结构化引用分开展示。

还没有完成：

- 大文件分片上传 UI、秒传和断点续传 UI。
- 文档删除、重建索引、任务重试按钮。
- 会话分页、搜索、重命名和删除。
- 管理端知识库、任务、评测报告和运行日志页面。
- 企业级前端认证会话管理，例如 refresh token 自动续期、路由守卫和角色菜单。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Element Plus
- lucide-vue 图标
- Vitest

## 前置条件

前端启动前，需要先准备后端：

1. 后端依赖已安装：

   ```bash
   uv sync
   ```

2. `.env` 已配置数据库、Redis、MinIO、Elasticsearch、Milvus、DashScope 等必要信息。

3. 本地 FastAPI 已启动：

   ```bash
   uv run fastapi dev know_engine_py/app/main.py --host 127.0.0.1 --port 8000
   ```

4. 如果要跑汽车演示知识库，先准备演示数据和文档：

   ```bash
   uv run python scripts/demo/seed_automotive_demo.py --write --create-tables
   uv run python scripts/demo/ingest_demo_documents.py --write --seed-demo-data --create-tables
   ```

5. 如果要观察文档索引任务，需要启动 Celery worker：

   ```bash
   uv run celery -A know_engine_py.app.tasks.celery_app.celery_app worker -l info
   ```

## 启动前端

进入前端目录：

```bash
cd know_engine_web
```

安装依赖：

```bash
npm install
```

启动开发服务：

```bash
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173/
```

默认后端地址是：

```text
http://127.0.0.1:8000
```

如果后端不在默认地址，可以在启动前设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## 演示账号

如果已经运行汽车演示数据脚本，可以使用：

```text
username: demo_user
password: DemoPassword123
knowledge base: demo-kb-automotive
```

登录后页面会自动加载当前用户可访问的知识库，不需要手填 `userId`。

## 推荐演示问题

```text
官方客服电话是多少？
Model Y 长续航版指导价是多少？
我的 Model Y 订单现在是什么状态？
我的车保养多少钱？
售后投诉处理规则是什么？
```

说明：

- “官方客服电话是多少？”主要验证文档检索和普通引用。
- “Model Y 长续航版指导价是多少？”主要验证 Text-to-SQL。
- “我的车保养多少钱？”可能触发车辆澄清卡片。
- “售后投诉处理规则是什么？”主要验证文档规则召回。

## 验证命令

类型检查：

```bash
npm run typecheck
```

单元测试：

```bash
npm test -- --run
```

生产构建：

```bash
npm run build
```

## 常见问题

### 1. 页面打不开 `http://127.0.0.1:5173/`

先确认 Vite 是否启动成功：

```bash
cd know_engine_web
npm run dev
```

如果 5173 被占用，Vite 会提示新的端口，以终端输出为准。

### 2. 页面显示 `Backend offline`

说明前端访问不到 FastAPI。先检查：

```bash
curl http://127.0.0.1:8000/health
```

如果后端不是 8000 端口，设置 `VITE_API_BASE_URL` 后重新启动前端。

### 3. 页面显示 `Backend degraded`

说明 FastAPI 可以访问，但数据库、Redis、MinIO、Elasticsearch 或 LLM 中至少一个组件不可用。

进入“管理控制台 / 环境健康中心”查看具体组件和处理建议。

### 4. 登录失败或提示数据库不可用

常见原因：

- FastAPI 未启动。
- `.env` 里的 `DATABASE_URL` 不可用。
- 云数据库网络断开或账号权限异常。
- 演示用户还没有通过 `seed_automotive_demo.py` 写入。

### 5. 聊天提示“大模型服务暂不可用”

常见原因：

- DashScope API key 未配置。
- 当前模型不可用或账号额度不足。
- `.env` 中 `LLM_CHAT_MODEL` 配到了不可用模型。

可以先切到可用模型，例如：

```text
LLM_CHAT_MODEL=qwen-turbo
```

修改 `.env` 后需要重启 FastAPI。

### 6. 控制台出现 Milvus deprecation warning

这是当前 Milvus / langchain-milvus 兼容层的技术债，不代表本次查询失败。

当前集合仍使用 JSON `metadata` 字段和 `metadata["groupId"]` 权限过滤；后续会迁移到 `enable_dynamic_field=True` 并重建演示集合。

## 分层说明

对应 Java/Spring 项目的视角：

- 本前端相当于独立的 Web Console，不放业务规则。
- `src/api/*` 类似前端侧 Feign/client 封装，只负责 HTTP 调用和响应转换。
- `src/components/*` 类似页面组件，不直接知道数据库、Celery、Milvus 等后端细节。
- 后端 `app/services/*` 仍是应用编排层，前端不绕过 API 直接操作消息、任务或索引。
