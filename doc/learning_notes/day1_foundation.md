# Day 1 学习笔记：FastAPI 项目骨架与配置管理

## 1. 当天目标

Day 1 的目标是搭建 Python 后端项目的最小运行闭环：

- 使用 FastAPI 创建 Web 应用。
- 提供 `/health` 健康检查接口。
- 使用 `pydantic-settings` 管理配置。
- 使用 pytest 验证接口行为和环境变量覆盖能力。
- 使用 uvicorn 启动服务，并通过真实 HTTP 请求验证。

这一天对应 Java/Spring Boot 项目的“启动类 + Controller + 配置类 + 测试环境”。

## 2. 当前文件结构

```text
konw-engine/
├── .venv/
├── pyproject.toml
├── uv.lock
├── .env.example
├── know_engine_py/
│   ├── __init__.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── health_router.py
│   │   └── core/
│   │       ├── __init__.py
│   │       └── settings.py
│   └── tests/
│       ├── test_health.py
│       └── test_settings.py
```

## 3. 为什么这样组织文件

### `pyproject.toml`

这是 Python 项目的项目配置文件，类似 Java 项目里的 `pom.xml` 或 `build.gradle`。

当前职责：

- 声明项目名、版本、Python 版本。
- 声明依赖：`fastapi`、`pydantic-settings`。
- 声明测试依赖：`pytest`、`pytest-asyncio`、`httpx`。
- 配置 pytest：
  - `testpaths = ["know_engine_py/tests"]`
  - `pythonpath = ["."]`

为什么放根目录：

- 当前 PyCharm 项目根目录就是 `konw-engine`。
- 根目录已有 `.venv`。
- 统一让 uv、PyCharm、pytest 都以根目录为项目根。

### `know_engine_py/app/main.py`

这是 FastAPI 应用入口，类似 Spring Boot 的启动类。

职责：

- 创建 `FastAPI` 应用对象。
- 注册各个 router。

当前代码核心：

```python
from fastapi import FastAPI

from know_engine_py.app.api.health_router import router as health_router

app = FastAPI(title="know-engine-py")
app.include_router(health_router)
```

为什么不把接口直接写在 `main.py`：

- `main.py` 只负责应用装配。
- 接口放到 `api/` 下，后面会有 `admin_router.py`、`document_router.py`、`chat_router.py`。
- 这类似 Java 中启动类不直接写业务接口，接口放在 `controller` 包里。

### `know_engine_py/app/api/health_router.py`

这是健康检查接口模块，类似 Java 的 `HealthController`。

职责：

- 定义 `/health` 接口。
- 返回当前应用状态和关键模型配置摘要。

当前代码核心：

```python
from fastapi import APIRouter

from know_engine_py.app.core.settings import get_settings

router = APIRouter()


@router.get("/health")
def health_check():
    settings = get_settings()

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.environment,
        "llm_chat_model": settings.llm_chat_model,
        "embedding_model": settings.embedding_model,
    }
```

为什么用 `APIRouter`：

- 它可以把一组接口拆成独立模块。
- `main.py` 通过 `include_router()` 注册。
- 后面每个业务域都可以有自己的 router。

### `know_engine_py/app/core/settings.py`

这是配置中心，类似 Spring Boot 的 `application.yml + @ConfigurationProperties`。

职责：

- 定义项目默认配置。
- 从 `.env` 或环境变量读取覆盖值。
- 通过 `get_settings()` 提供全局配置对象。

当前代码核心：

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "know-engine-py"
    environment: str = "local"

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    llm_chat_model: str = "qwen-plus"
    llm_fast_model: str = "qwen-turbo"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

为什么用 `pydantic-settings`：

- 自动把环境变量映射到 Python 字段。
- 自动做类型转换，例如 `"1024"` 转成 `int`。
- 和 Pydantic 生态一致，后续 FastAPI schema 也使用 Pydantic。

为什么用 `@lru_cache`：

- `Settings()` 会读取环境变量和 `.env`。
- 配置对象通常不需要每次请求都重新创建。
- `@lru_cache` 让 `get_settings()` 第一次创建后复用同一个对象。

### `know_engine_py/tests/test_health.py`

这是接口行为测试。

职责：

- 用 FastAPI 的 `TestClient` 模拟 HTTP 请求。
- 验证 `/health` 返回 200。
- 验证响应 JSON 符合预期。

核心语法：

```python
client = TestClient(app)
response = client.get("/health")
assert response.status_code == 200
```

### `know_engine_py/tests/test_settings.py`

这是配置覆盖测试。

职责：

- 使用 pytest 的 `monkeypatch` 临时设置环境变量。
- 验证环境变量能覆盖 `Settings` 默认值。
- 清理 `get_settings()` 的缓存，避免测试之间相互污染。

核心语法：

```python
monkeypatch.setenv("APP_NAME", "know-engine-test")
get_settings.cache_clear()
settings = get_settings()
```

## 4. Python 语法要点

### 包和 `__init__.py`

Python 通过目录组织模块。

`__init__.py` 的作用是告诉 Python：这个目录可以作为包导入。

例如：

```python
from know_engine_py.app.main import app
```

要求这些目录能被 Python 识别：

- `know_engine_py/`
- `know_engine_py/app/`

### 类型注解

示例：

```python
app_name: str = "know-engine-py"
embedding_dimensions: int = 1024
```

含义：

- `app_name` 期望是字符串。
- `embedding_dimensions` 期望是整数。
- Pydantic 会利用这些类型信息做校验和转换。

### 类继承

示例：

```python
class Settings(BaseSettings):
```

含义：

- `Settings` 继承 `BaseSettings`。
- 因此 `Settings` 获得了读取环境变量、读取 `.env`、类型转换等能力。

### 装饰器

示例：

```python
@router.get("/health")
def health_check():
```

含义：

- 把 `health_check` 函数注册为一个 HTTP GET 接口。
- 路径是 `/health`。

另一个例子：

```python
@lru_cache
def get_settings() -> Settings:
```

含义：

- 缓存函数返回结果。
- 第二次调用时，如果参数一样，直接返回缓存值。

## 5. FastAPI 概念

### `FastAPI`

`FastAPI` 是应用对象，类似 Spring Boot 启动后的 Web 容器入口。

### `APIRouter`

`APIRouter` 用来组织接口。

类比 Java：

- `main.py` 类似启动类。
- `health_router.py` 类似 `HealthController`。
- `include_router()` 类似把 controller 注册进应用上下文。

### `TestClient`

`TestClient` 可以在不真正启动 uvicorn 的情况下测试 HTTP 接口。

它适合单元测试和接口测试。

## 6. pydantic-settings 概念

环境变量名和字段名的对应关系：

```text
APP_NAME              -> app_name
ENVIRONMENT           -> environment
DASHSCOPE_BASE_URL    -> dashscope_base_url
LLM_CHAT_MODEL        -> llm_chat_model
EMBEDDING_DIMENSIONS  -> embedding_dimensions
```

默认情况下，pydantic-settings 会读取环境变量，也可以通过 `env_file=".env"` 读取 `.env` 文件。

当前项目只创建了 `.env.example`，还没有创建真实 `.env`。这是合理的，因为目前还没有真正调用 DashScope。

## 7. 验证命令

运行测试：

```bash
uv run pytest know_engine_py/tests -q
```

预期：

```text
2 passed
```

启动服务：

```bash
uv run uvicorn know_engine_py.app.main:app --reload
```

访问健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期：

```json
{
  "status": "ok",
  "app_name": "know-engine-py",
  "environment": "local",
  "llm_chat_model": "qwen-plus",
  "embedding_model": "text-embedding-v4"
}
```

## 8. Day 1 面试可讲点

- 我使用 FastAPI 搭建了 Python 后端项目骨架，并将路由按模块拆分，避免所有接口堆在入口文件中。
- 我使用 `pydantic-settings` 管理配置，支持默认值、环境变量覆盖和 `.env` 文件读取，类似 Spring Boot 的配置绑定能力。
- 我用 pytest 先写测试，再实现 `/health` 接口，验证了接口行为和配置覆盖能力。
- 我将虚拟环境、`pyproject.toml`、`uv.lock` 统一放在 PyCharm 项目根目录，避免子项目环境混乱。

