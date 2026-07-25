from app.services.vector_db_service import (
    search_similar_chunks,
)


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
        "app.services.vector_db_service.collection.query",
        lambda **kwargs: fake_results,
    )

    chunks = search_similar_chunks(
        question="Pregunta de prueba",
        max_distance=1.2,
    )

    assert chunks == [
        "Chunk relevante"
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