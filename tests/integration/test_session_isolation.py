from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.services.openai_service import CitedAnswer
from app.services.vector_db_service import (
    cleanup_expired_documents,
    find_document_by_hash,
    get_collection,
    save_chunks,
)


SESSION_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SESSION_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _save_document(
    *,
    session_id: str,
    filename: str,
    file_hash: str,
    created_at: datetime | None = None,
    chunk_count: int = 1,
) -> str:
    return save_chunks(
        chunks_with_embeddings=[
            {
                "text": f"Contenido privado de {filename}, fragmento {index}.",
                "page_number": index + 1,
                "embedding": [1.0, float(index)],
            }
            for index in range(chunk_count)
        ],
        filename=filename,
        file_hash=file_hash,
        session_id=session_id,
        created_at=created_at,
    )


def test_valid_session_id_is_accepted(client: TestClient) -> None:
    response = client.get(
        "/documents",
        headers={"X-Session-ID": SESSION_A},
    )

    assert response.status_code == 200
    assert response.json() == {"documents": []}


def test_missing_session_id_returns_controlled_error(
    client: TestClient,
) -> None:
    client.headers.pop("X-Session-ID")

    response = client.get("/documents")

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_session",
        "message": "Falta el identificador de sesión X-Session-ID.",
    }


def test_invalid_session_id_returns_controlled_error(
    client: TestClient,
) -> None:
    response = client.get(
        "/documents",
        headers={"X-Session-ID": "not-a-uuid"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session"


def test_session_cannot_list_another_sessions_documents(
    client: TestClient,
) -> None:
    own_document_id = _save_document(
        session_id=SESSION_A,
        filename="sesion-a.pdf",
        file_hash="hash-a",
    )
    _save_document(
        session_id=SESSION_B,
        filename="sesion-b.pdf",
        file_hash="hash-b",
    )

    response = client.get(
        "/documents",
        headers={"X-Session-ID": SESSION_A},
    )

    assert response.status_code == 200
    assert [item["document_id"] for item in response.json()["documents"]] == [
        own_document_id
    ]
    assert "sesion-b.pdf" not in response.text


def test_sha256_deduplication_is_scoped_to_session() -> None:
    own_document_id = _save_document(
        session_id=SESSION_A,
        filename="same.pdf",
        file_hash="same-hash",
    )

    assert find_document_by_hash("same-hash", SESSION_A) == own_document_id
    assert find_document_by_hash("same-hash", SESSION_B) is None


def test_session_cannot_chat_with_another_sessions_document(
    client: TestClient,
) -> None:
    other_document_id = _save_document(
        session_id=SESSION_B,
        filename="sesion-b.pdf",
        file_hash="hash-b",
    )

    response = client.post(
        "/chat/document",
        headers={"X-Session-ID": SESSION_A},
        json={"message": "Pregunta", "document_id": other_document_id},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_global_chat_only_retrieves_current_session_chunks(
    client: TestClient,
    monkeypatch,
) -> None:
    _save_document(
        session_id=SESSION_A,
        filename="sesion-a.pdf",
        file_hash="hash-a",
    )
    _save_document(
        session_id=SESSION_B,
        filename="sesion-b.pdf",
        file_hash="hash-b",
    )
    received_chunks: list[dict] = []

    monkeypatch.setattr(
        "app.services.vector_db_service.generate_embedding",
        lambda question: [1.0, 0.0],
    )

    def fake_generate_cited_response(
        question: str,
        chunks: list[dict],
    ) -> CitedAnswer:
        received_chunks.extend(chunks)
        return CitedAnswer(answer="Respuesta [[S1]].", source_ids=["S1"])

    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        fake_generate_cited_response,
    )

    response = client.post(
        "/chat",
        headers={"X-Session-ID": SESSION_A},
        json={"message": "Pregunta"},
    )

    assert response.status_code == 200
    assert received_chunks
    assert {chunk["filename"] for chunk in received_chunks} == {
        "sesion-a.pdf"
    }


def test_saved_chunks_include_session_and_retention_metadata() -> None:
    created_at = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    document_id = _save_document(
        session_id=SESSION_A,
        filename="metadata.pdf",
        file_hash="hash-metadata",
        created_at=created_at,
        chunk_count=2,
    )

    stored = get_collection().get(
        where={"document_id": document_id},
        include=["metadatas"],
    )

    assert len(stored["ids"]) == 2
    for metadata in stored["metadatas"]:
        assert metadata["session_id"] == SESSION_A
        assert metadata["document_id"] == document_id
        assert metadata["filename"] == "metadata.pdf"
        assert metadata["page"] in {1, 2}
        assert metadata["created_at"] == "2026-08-28T12:00:00+00:00"
        assert metadata["expires_at"] == "2026-08-29T12:00:00+00:00"


def test_expiration_deletes_all_expired_chunks_and_keeps_active_documents() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    expired_document_id = _save_document(
        session_id=SESSION_A,
        filename="expired.pdf",
        file_hash="hash-expired",
        created_at=now - timedelta(hours=25),
        chunk_count=2,
    )
    active_document_id = _save_document(
        session_id=SESSION_A,
        filename="active.pdf",
        file_hash="hash-active",
        created_at=now - timedelta(hours=23),
        chunk_count=2,
    )

    assert cleanup_expired_documents(now=now) == 1

    expired = get_collection().get(where={"document_id": expired_document_id})
    active = get_collection().get(where={"document_id": active_document_id})
    assert expired["ids"] == []
    assert len(active["ids"]) == 2
