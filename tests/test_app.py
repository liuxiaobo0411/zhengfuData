from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_page_loads():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "工作台" in response.text
