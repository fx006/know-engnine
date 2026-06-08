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
    eval_llm_model: str = "qwen-max"
    eval_embedding_model: str = "text-embedding-v4"
    eval_max_concurrency: int = 2
    eval_output_dir: str = "eval/reports"
    eval_llm_max_tokens: int = 10240
    eval_input_cost_per_1k_tokens: float = 0.0
    eval_output_cost_per_1k_tokens: float = 0.0
    eval_cost_currency: str = "CNY"
    ragas_do_not_track: bool = True

    database_url: str = "sqlite+aiosqlite:///:memory:"
    database_echo: bool = False
    mysql_test_database_url: str = ""

    jwt_secret_key: str = "change-me-to-a-32-byte-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    redis_url: str = ""

    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "know-engine"
    minio_secure: bool = False

    elasticsearch_url: str = ""
    elasticsearch_index: str = "know_engine_segments"

    milvus_uri: str = ""
    milvus_collection: str = "know_engine_segments"

    mineru_base_url: str = ""
    mineru_api_key: str = ""

    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""

    celery_broker_url: str = ""
    celery_result_backend: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
