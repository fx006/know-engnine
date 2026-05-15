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

    database_url: str = "sqlite+aiosqlite:///:memory:"
    database_echo: bool = False
    mysql_test_database_url: str = ""

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
