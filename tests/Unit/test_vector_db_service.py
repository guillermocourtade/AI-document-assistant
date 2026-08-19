from app.services.vector_db_service import (
    count_document_chunks,
    find_document_by_hash,
    list_documents,
    search_similar_chunks,
)


class FakeCollection:
    def __init__(self, results):
        self.results = results

    def query(self, **kwargs):
        return self.results

    def get(self, **kwargs):
        return self.results


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

    monkeypatch.setattr(
        "app.services.vector_db_service.get_collection",
        lambda: FakeCollection(fake_results),
    )

    chunks = search_similar_chunks(
        question="Pregunta de prueba",
        max_distance=1.2,
    )

    assert chunks == [
        "Chunk relevante"
    ]


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

    document_id = find_document_by_hash("abc123")

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

    assert count_document_chunks("documento-existente") == 2


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

    assert list_documents() == [
        {
            "document_id": "documento-1",
            "filename": "uno.pdf",
            "chunks_saved": 2,
        },
        {
            "document_id": "documento-2",
            "filename": "dos.pdf",
            "chunks_saved": 1,
        },
    ]

import pytest

from app.exceptions.custom_exceptions import (
    DocumentNotFoundError,
)
from app.services.vector_db_service import (
    search_similar_chunks,
)


def test_search_raises_when_document_does_not_exist(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.vector_db_service.document_exists",
        lambda document_id: False,
    )

    with pytest.raises(
        DocumentNotFoundError,
        match="No existe un documento",
    ):
        search_similar_chunks(
            question="Pregunta",
            document_id="documento-inexistente",
        )
