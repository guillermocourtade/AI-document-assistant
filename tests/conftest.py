import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """
    Crea un cliente HTTP de prueba para la aplicación FastAPI.

    El cliente permite probar los endpoints sin iniciar Uvicorn.
    """
    with TestClient(app) as test_client:
        yield test_client