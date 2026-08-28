import pytest
from fastapi.testclient import TestClient


TEST_SESSION_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def isolated_vector_db(tmp_path, monkeypatch):
    db_path = tmp_path / "chroma_db"

    monkeypatch.setenv("CHROMA_DB_PATH", str(db_path))

    from app.services import vector_db_service
    from app.rate_limit import rate_limiter

    vector_db_service.configure_vector_db(str(db_path))
    rate_limiter.reset()

    yield

    vector_db_service.configure_vector_db(str(db_path))
    rate_limiter.reset()


@pytest.fixture
def client(isolated_vector_db) -> TestClient:
    """
    Crea un cliente HTTP de prueba para la aplicación FastAPI.

    El cliente permite probar los endpoints sin iniciar Uvicorn.
    """
    from app.main import app

    with TestClient(app) as test_client:
        test_client.headers["X-Session-ID"] = TEST_SESSION_ID
        yield test_client
