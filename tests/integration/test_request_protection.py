from fastapi.testclient import TestClient

from app.exceptions.custom_exceptions import (
    AIServiceTimeoutError,
    ServiceBusyError,
)
from app.services.openai_service import CitedAnswer


def _stub_successful_chat(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        lambda question, chunks: CitedAnswer(
            answer="No se encontró información relevante en los documentos.",
            source_ids=[],
        ),
    )


def test_chat_endpoints_share_rate_limit_and_return_safe_429(
    client: TestClient,
    monkeypatch,
) -> None:
    logged_events = []
    _stub_successful_chat(monkeypatch)
    monkeypatch.setattr("app.rate_limit.CHAT_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(
        "app.rate_limit.log_event",
        lambda event, **fields: logged_events.append((event, fields)),
    )

    first_response = client.post(
        "/chat",
        json={"message": "Primera pregunta"},
    )
    rejected_response = client.post(
        "/chat/document",
        json={
            "message": "contenido sensible que no debe registrarse",
            "document_id": "documento-secreto",
        },
    )

    assert first_response.status_code == 200
    assert rejected_response.status_code == 429
    assert rejected_response.json() == {
        "error": {
            "code": "rate_limit_exceeded",
            "message": (
                "Se excedió el límite de solicitudes. Inténtalo más tarde."
            ),
        }
    }
    assert logged_events == [
        (
            "request_rejected",
            {
                "endpoint": "/chat/document",
                "reason": "rate_limit",
            },
        )
    ]
    assert "sensible" not in str(logged_events)
    assert "documento-secreto" not in str(logged_events)


def test_upload_has_independent_rate_limit(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.rate_limit.UPLOAD_RATE_LIMIT_REQUESTS", 1)

    first_response = client.post(
        "/upload",
        files={"file": ("invalid.pdf", b"invalid", "application/pdf")},
    )
    rejected_response = client.post(
        "/upload",
        files={"file": ("invalid.pdf", b"invalid", "application/pdf")},
    )

    assert first_response.status_code == 400
    assert rejected_response.status_code == 429
    assert rejected_response.json()["error"]["code"] == (
        "rate_limit_exceeded"
    )


def test_openai_timeout_returns_safe_504_and_keeps_observability(
    client: TestClient,
    monkeypatch,
) -> None:
    logged_rag_events = []
    sensitive_detail = "OPENAI_API_KEY=must-not-leak"
    results = [
        {
            "source_id": "S1",
            "text": "Contenido",
            "filename": "manual.pdf",
            "page_number": 1,
            "chunk_index": 0,
        }
    ]

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda *args, **kwargs: results,
    )

    def raise_timeout(question, chunks):
        raise AIServiceTimeoutError(
            "El servicio de IA excedió el tiempo de espera."
        ) from RuntimeError(sensitive_detail)

    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        raise_timeout,
    )
    monkeypatch.setattr(
        "app.observability.log_event",
        lambda event, **fields: logged_rag_events.append((event, fields)),
    )

    response = client.post(
        "/chat",
        json={"message": "Pregunta privada"},
    )

    assert response.status_code == 504
    assert response.json() == {
        "error": {
            "code": "ai_service_timeout",
            "message": "El servicio de IA excedió el tiempo de espera.",
        }
    }
    assert sensitive_detail not in response.text
    assert "Traceback" not in response.text

    event, fields = logged_rag_events[0]
    assert event == "rag_request_completed"
    assert fields["status"] == "error"
    assert fields["error_type"] == "AIServiceTimeoutError"
    assert sensitive_detail not in str(fields)


def test_openai_concurrency_rejection_returns_safe_503(
    client: TestClient,
    monkeypatch,
) -> None:
    sensitive_detail = "internal-pool-state"
    results = [
        {
            "source_id": "S1",
            "text": "Contenido",
            "filename": "manual.pdf",
            "page_number": 1,
            "chunk_index": 0,
        }
    ]

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda *args, **kwargs: results,
    )

    def raise_busy(question, chunks):
        raise ServiceBusyError(
            "El servicio de IA está temporalmente ocupado. "
            "Inténtalo más tarde."
        ) from RuntimeError(sensitive_detail)

    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        raise_busy,
    )

    response = client.post(
        "/chat",
        json={"message": "Pregunta privada"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_busy",
            "message": (
                "El servicio de IA está temporalmente ocupado. "
                "Inténtalo más tarde."
            ),
        }
    }
    assert sensitive_detail not in response.text
    assert "Traceback" not in response.text
