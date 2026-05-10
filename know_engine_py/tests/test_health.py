from fastapi.testclient import TestClient

from know_engine_py.app.main import app


def test_health_returns_application_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "know-engine-py",
        "environment": "local",
        "llm_chat_model": "qwen-plus",
        "embedding_model": "text-embedding-v4",
    }
