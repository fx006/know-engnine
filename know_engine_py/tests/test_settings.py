from know_engine_py.app.core.settings import get_settings


def test_settings_can_be_overridden_by_environment(monkeypatch):
    get_settings.cache_clear()

    monkeypatch.setenv("APP_NAME", "know-engine-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LLM_CHAT_MODEL", "qwen-max")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.setenv(
        "MYSQL_TEST_DATABASE_URL",
        "mysql+asyncmy://root:password@127.0.0.1:3306/know_engine?charset=utf8mb4",
    )
    monkeypatch.setenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    settings=get_settings()

    assert settings.app_name=="know-engine-test"
    assert settings.environment=="test"
    assert settings.llm_chat_model=="qwen-max"
    assert settings.embedding_model=="text-embedding-v4"
    assert settings.dashscope_base_url=="https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.mysql_test_database_url=="mysql+asyncmy://root:password@127.0.0.1:3306/know_engine?charset=utf8mb4"

    get_settings.cache_clear()
