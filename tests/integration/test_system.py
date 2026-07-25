from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """
    Verifica que el endpoint raíz responda correctamente.
    """
    response = client.get("/")

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_health_endpoint(client: TestClient) -> None:
    """
    Verifica el contrato HTTP básico del endpoint /health.
    """
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, dict)
    assert body["status"] == "ok"


def test_about_endpoint(client: TestClient) -> None:
    response = client.get("/about")

    assert response.status_code == 200
    assert response.json() == {
        "message": "This is an AI Document Assistant API built with FastAPI."
    }