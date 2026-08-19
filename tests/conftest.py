import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_vector_db(tmp_path, monkeypatch):
    db_path = tmp_path / "chroma_db"

    monkeypatch.setenv("CHROMA_DB_PATH", str(db_path))

    from app.services import vector_db_service

    vector_db_service.configure_vector_db(str(db_path))

    yield

    vector_db_service.configure_vector_db(str(db_path))


@pytest.fixture
def client(isolated_vector_db) -> TestClient:
    """
    Crea un cliente HTTP de prueba para la aplicación FastAPI.

    El cliente permite probar los endpoints sin iniciar Uvicorn.
    """
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
