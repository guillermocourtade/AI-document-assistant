import pytest
from datetime import datetime, timezone

from app.exceptions.custom_exceptions import (
    DocumentPageLimitExceededError,
    DocumentNotFoundError,
)
from app.services.vector_db_service import (
    cleanup_expired_documents,
    count_document_chunks,
    count_session_pages,
    find_document_by_hash,
    list_documents,
    reserve_session_page_capacity,
    save_chunks,
    search_similar_chunks,
    search_similar_chunks_with_metadata,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"


class FakeCollection:
    def __init__(self, results):
        self.results = results
        self.query_arguments = None

    def query(self, **kwargs):
        self.query_arguments = kwargs
        return self.results

    def get(self, **kwargs):
        return self.results


class FakeWritableCollection:
    def __init__(self):
        self.add_arguments = None

    def add(self, **kwargs):
        self.add_arguments = kwargs


def test_search_filters_chunks_by_distance(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.vector_db_service.generate_embedding",
        lambda question: [0.1, 0.2],
    )

    fake_results = {
        "documents": [
            [
                "Chunk relevante",
                "Chunk irrelevante",
            ]
        ],
        "distances": [
            [
                0.8,
                1.8,
            ]
        ],
    }

    fake_collection = FakeCollection(fake_results)

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: fake_collection,
    )

    chunks = search_similar_chunks(
        question="Pregunta de prueba",
        session_id=SESSION_ID,
        max_distance=1.2,
    )

    assert chunks == [
        "Chunk relevante"
    ]
    assert fake_collection.query_arguments["n_results"] == 6


def test_find_document_by_hash_returns_existing_document(
    monkeypatch,
):
    fake_results = {
        "metadatas": [
            {
                "document_id": "documento-existente",
                "file_hash": "abc123",
            }
        ]
    }

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: FakeCollection(fake_results),
    )

    document_id = find_document_by_hash("abc123", SESSION_ID)

    assert document_id == "documento-existente"


def test_count_document_chunks_returns_collection_count(
    monkeypatch,
):
    fake_results = {
        "ids": [
            "chunk-1",
            "chunk-2",
        ]
    }

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: FakeCollection(fake_results),
    )

    assert count_document_chunks("documento-existente", SESSION_ID) == 2


def test_list_documents_groups_chunks_by_document(
    monkeypatch,
):
    fake_results = {
        "metadatas": [
            {
                "document_id": "documento-1",
                "filename": "uno.pdf",
            },
            {
                "document_id": "documento-1",
                "filename": "uno.pdf",
            },
            {
                "document_id": "documento-2",
                "filename": "dos.pdf",
            },
        ]
    }

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: FakeCollection(fake_results),
    )

    assert list_documents(SESSION_ID) == [
        {
            "document_id": "documento-1",
            "filename": "uno.pdf",
            "chunks_saved": 2,
            "created_at": None,
            "expires_at": None,
        },
        {
            "document_id": "documento-2",
            "filename": "dos.pdf",
            "chunks_saved": 1,
            "created_at": None,
            "expires_at": None,
        },
    ]


def test_save_chunks_persists_page_number_with_existing_metadata(
    monkeypatch,
):
    fake_collection = FakeWritableCollection()

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: fake_collection,
    )

    document_id = save_chunks(
        chunks_with_embeddings=[
            {
                "text": "Contenido de la página dos",
                "page_number": 2,
                "embedding": [0.1, 0.2],
            },
            {
                "text": "Contenido de la página tres",
                "page_number": 3,
                "embedding": [0.3, 0.4],
            },
        ],
        filename="documento.pdf",
        file_hash="hash-sha256",
        session_id=SESSION_ID,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert fake_collection.add_arguments["metadatas"] == [
        {
            "session_id": SESSION_ID,
            "document_id": document_id,
            "filename": "documento.pdf",
            "file_hash": "hash-sha256",
            "chunk_index": 0,
            "page": 2,
            "page_number": 2,
            "page_count": 3,
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2026-01-02T00:00:00+00:00",
        },
        {
            "session_id": SESSION_ID,
            "document_id": document_id,
            "filename": "documento.pdf",
            "file_hash": "hash-sha256",
            "chunk_index": 1,
            "page": 3,
            "page_number": 3,
            "page_count": 3,
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2026-01-02T00:00:00+00:00",
        },
    ]


def test_count_session_pages_counts_each_document_once_and_supports_legacy(
    monkeypatch,
):
    fake_results = {
        "metadatas": [
            {"document_id": "documento-1", "page_count": 8, "page": 1},
            {"document_id": "documento-1", "page_count": 8, "page": 8},
            {"document_id": "documento-2", "page_number": 2},
            {"document_id": "documento-2", "page_number": 5},
        ]
    }
    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: FakeCollection(fake_results),
    )

    assert count_session_pages(SESSION_ID) == 13


def test_reserve_session_page_capacity_rejects_excess(monkeypatch):
    monkeypatch.setattr(
        "app.services.vector_db_service.count_session_pages",
        lambda session_id: 299,
    )

    with pytest.raises(
        DocumentPageLimitExceededError,
        match="quedan 1 disponibles",
    ):
        with reserve_session_page_capacity(SESSION_ID, 2, 300):
            pass


def test_search_raises_when_document_does_not_exist(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.vector_db_service.document_exists",
        lambda document_id, session_id: False,
    )

    with pytest.raises(
        DocumentNotFoundError,
        match="No existe un documento",
    ):
        search_similar_chunks(
            question="Pregunta",
            session_id=SESSION_ID,
            document_id="documento-inexistente",
        )


def test_structured_search_returns_metadata_and_filters_distance(
    monkeypatch,
):
    fake_collection = FakeCollection(
        {
            "documents": [["Chunk relevante", "Chunk lejano"]],
            "distances": [[0.7, 1.8]],
            "metadatas": [
                [
                    {
                        "filename": "manual.pdf",
                        "page_number": 2,
                        "chunk_index": 7,
                    },
                    {
                        "filename": "manual.pdf",
                        "page_number": 5,
                    },
                ]
            ],
        }
    )

    monkeypatch.setattr(
        "app.services.vector_db_service.generate_embedding",
        lambda question: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: fake_collection,
    )

    results = search_similar_chunks_with_metadata(
        question="Pregunta",
        session_id=SESSION_ID,
        max_distance=1.2,
    )

    assert results == [
        {
            "source_id": "S1",
            "text": "Chunk relevante",
            "filename": "manual.pdf",
            "page_number": 2,
            "chunk_index": 7,
        }
    ]
    assert fake_collection.query_arguments["include"] == [
        "documents",
        "distances",
        "metadatas",
    ]
    assert fake_collection.query_arguments["n_results"] == 6
    assert fake_collection.query_arguments["where"] == {
        "session_id": SESSION_ID,
    }


def test_structured_search_filters_document_and_handles_legacy_metadata(
    monkeypatch,
):
    fake_collection = FakeCollection(
        {
            "documents": [["Chunk de documento antiguo"]],
            "distances": [[0.5]],
            "metadatas": [[{"filename": "antiguo.pdf"}]],
        }
    )

    monkeypatch.setattr(
        "app.services.vector_db_service.document_exists",
        lambda document_id, session_id: True,
    )
    monkeypatch.setattr(
        "app.services.vector_db_service.generate_embedding",
        lambda question: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: fake_collection,
    )

    results = search_similar_chunks_with_metadata(
        question="Pregunta",
        session_id=SESSION_ID,
        document_id="documento-antiguo",
    )

    assert results == [
        {
            "source_id": "S1",
            "text": "Chunk de documento antiguo",
            "filename": "antiguo.pdf",
            "page_number": None,
            "chunk_index": None,
        }
    ]
    assert fake_collection.query_arguments["where"] == {
        "$and": [
            {"session_id": SESSION_ID},
            {"document_id": "documento-antiguo"},
        ],
    }
