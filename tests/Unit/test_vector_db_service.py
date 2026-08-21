import pytest

from app.exceptions.custom_exceptions import (
    DocumentNotFoundError,
)
from app.services.vector_db_service import (
    count_document_chunks,
    find_document_by_hash,
    list_documents,
    save_chunks,
    search_similar_chunks,
    search_similar_chunks_with_metadata,
)


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
    )

    assert fake_collection.add_arguments["metadatas"] == [
        {
            "document_id": document_id,
            "filename": "documento.pdf",
            "file_hash": "hash-sha256",
            "chunk_index": 0,
            "page_number": 2,
        },
        {
            "document_id": document_id,
            "filename": "documento.pdf",
            "file_hash": "hash-sha256",
            "chunk_index": 1,
            "page_number": 3,
        },
    ]


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
        max_distance=1.2,
    )

    assert results == [
        {
            "text": "Chunk relevante",
            "filename": "manual.pdf",
            "page_number": 2,
        }
    ]
    assert fake_collection.query_arguments["include"] == [
        "documents",
        "distances",
        "metadatas",
    ]
    assert fake_collection.query_arguments["n_results"] == 6
    assert "where" not in fake_collection.query_arguments


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
        lambda document_id: True,
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
        document_id="documento-antiguo",
    )

    assert results == [
        {
            "text": "Chunk de documento antiguo",
            "filename": "antiguo.pdf",
            "page_number": None,
        }
    ]
    assert fake_collection.query_arguments["where"] == {
        "document_id": "documento-antiguo",
    }
