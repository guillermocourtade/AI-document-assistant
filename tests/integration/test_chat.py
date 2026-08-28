from typing import Any

from fastapi.testclient import TestClient

from app.services.openai_service import CitedAnswer


def test_chat_endpoint_returns_generated_answer(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """
    Verifica el flujo exitoso de POST /chat sin llamar
    realmente a ChromaDB ni a OpenAI.
    """

    received_data: dict[str, object] = {}

    def fake_search_similar_chunks_with_metadata(
        question: str,
        session_id: str,
        n_results: int = 6,
    ) -> list[dict]:
        received_data["search_question"] = question
        received_data["n_results"] = n_results

        return [
            {
                "source_id": "S1",
                "text": "Python fue creado por Guido van Rossum.",
                "filename": "python.pdf",
                "page_number": 2,
                "chunk_index": 1,
            },
            {
                "source_id": "S2",
                "text": "La primera versión pública apareció en 1991.",
                "filename": "python.pdf",
                "page_number": 2,
                "chunk_index": 2,
            },
            {
                "source_id": "S3",
                "text": "Python es un lenguaje interpretado.",
                "filename": "historia.pdf",
                "page_number": 5,
                "chunk_index": 3,
            },
        ]

    def fake_generate_cited_response(
        question: str,
        chunks: list[dict],
    ) -> CitedAnswer:
        received_data["generation_question"] = question
        received_data["generation_chunks"] = chunks

        return CitedAnswer(
            answer="Python fue creado por Guido van Rossum [[S1]].",
            source_ids=["S1"],
        )

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        fake_search_similar_chunks_with_metadata,
    )

    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        fake_generate_cited_response,
    )

    request_body = {
        "message": "¿Quién creó Python?",
    }

    response = client.post(
        "/chat",
        json=request_body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Python fue creado por Guido van Rossum [p. 2].",
        "sources": [
            {
                "filename": "python.pdf",
                "page_number": 2,
            },
        ],
    }

    assert received_data["search_question"] == "¿Quién creó Python?"
    assert received_data["generation_question"] == "¿Quién creó Python?"

    assert received_data["generation_chunks"][0]["source_id"] == "S1"
    assert received_data["generation_chunks"][0]["page_number"] == 2


def test_chat_endpoint_returns_fallback_when_no_chunks_are_found(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """
    Verifica el flujo cuando el retrieval no encuentra
    fragmentos relevantes.
    """

    def fake_search_similar_chunks_with_metadata(
        question: str,
        session_id: str,
        n_results: int = 6,
    ) -> list[dict]:
        return []

    def fake_generate_cited_response(
        question: str,
        chunks: list[dict],
    ) -> CitedAnswer:
        assert chunks == []

        return CitedAnswer(
            answer="No se encontró información relevante en los documentos.",
            source_ids=[],
        )

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        fake_search_similar_chunks_with_metadata,
    )

    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        fake_generate_cited_response,
    )

    response = client.post(
        "/chat",
        json={
            "message": "¿Cuál es la capital de Marte?",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "No se encontró información relevante en los documentos.",
        "sources": [],
    }


def test_document_chat_returns_sources_and_text_only_context(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    received_data: dict[str, object] = {}

    def fake_search_similar_chunks_with_metadata(
        question: str,
        session_id: str,
        n_results: int = 6,
        document_id: str | None = None,
        max_distance: float = 1.2,
    ) -> list[dict]:
        received_data["search_document_id"] = document_id

        return [
            {
                "source_id": "S1",
                "text": "Contenido del documento antiguo.",
                "filename": "antiguo.pdf",
                "page_number": None,
                "chunk_index": None,
            }
        ]

    def fake_generate_cited_response(
        question: str,
        chunks: list[dict],
    ) -> CitedAnswer:
        received_data["generation_chunks"] = chunks
        return CitedAnswer(
            answer="Respuesta del documento [[S1]].",
            source_ids=["S1"],
        )

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        fake_search_similar_chunks_with_metadata,
    )
    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        fake_generate_cited_response,
    )

    response = client.post(
        "/chat/document",
        json={
            "message": "Pregunta del documento",
            "document_id": "documento-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Respuesta del documento [fuente sin página].",
        "document_id": "documento-1",
        "sources": [
            {
                "filename": "antiguo.pdf",
                "page_number": None,
            }
        ],
    }
    assert received_data["search_document_id"] == "documento-1"
    assert received_data["generation_chunks"] == [
        {
            "source_id": "S1",
            "text": "Contenido del documento antiguo.",
            "filename": "antiguo.pdf",
            "page_number": None,
            "chunk_index": None,
        }
    ]


def test_chat_discards_invented_ids_and_model_page_numbers(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    results = [
        {
            "source_id": "S1",
            "text": "El empleado debe avisar con 30 días de anticipación.",
            "filename": "reglamento.pdf",
            "page_number": 13,
            "chunk_index": 81,
        }
    ]

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda question, session_id, n_results=6: results,
    )
    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        lambda question, chunks: CitedAnswer(
            answer=(
                "El empleado debe avisar con 30 días [p. 999] [[S999]] "
                "de anticipación [[S1]]."
            ),
            source_ids=["S999", "S1"],
        ),
    )

    response = client.post(
        "/chat",
        json={"message": "¿Cuándo debe avisar?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "El empleado debe avisar con 30 días de anticipación [p. 13]."
        ),
        "sources": [
            {
                "filename": "reglamento.pdf",
                "page_number": 13,
            }
        ],
    }


def test_chat_normalizes_only_validated_citation_format(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    results = [
        {
            "source_id": "S1",
            "text": "Primera fuente.",
            "filename": "manual.pdf",
            "page_number": 6,
            "chunk_index": 1,
        },
        {
            "source_id": "S2",
            "text": "Segunda fuente.",
            "filename": "manual.pdf",
            "page_number": 12,
            "chunk_index": 2,
        },
        {
            "source_id": "S3",
            "text": "Tercera fuente de la misma página.",
            "filename": "manual.pdf",
            "page_number": 12,
            "chunk_index": 3,
        },
        {
            "source_id": "S4",
            "text": "Fuente de una página distinta.",
            "filename": "manual.pdf",
            "page_number": 13,
            "chunk_index": 4,
        },
    ]

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda question, session_id, n_results=6: results,
    )
    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        lambda question, chunks: CitedAnswer(
            answer=(
                "Se concede un día[[S1]]. "
                "La regla adicional [[S2]][[S3]][[S4]]."
            ),
            source_ids=["S1", "S2", "S3", "S4"],
        ),
    )

    response = client.post("/chat", json={"message": "Pregunta"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "Se concede un día [p. 6]. "
            "La regla adicional [p. 12] [p. 13]."
        ),
        "sources": [
            {"filename": "manual.pdf", "page_number": 6},
            {"filename": "manual.pdf", "page_number": 12},
            {"filename": "manual.pdf", "page_number": 13},
        ],
    }


def test_chat_endpoint_rejects_missing_message(
    client: TestClient,
) -> None:
    """
    Verifica que Pydantic rechace un body que no contiene
    el campo obligatorio message.
    """

    response = client.post(
        "/chat",
        json={},
    )

    assert response.status_code == 422

    body = response.json()

    assert "detail" in body
    assert isinstance(body["detail"], list)


def test_chat_endpoint_rejects_invalid_message_type(
    client: TestClient,
) -> None:
    """
    Verifica que el endpoint rechace un tipo de dato inválido.
    """

    response = client.post(
        "/chat",
        json={
            "message": {
                "invalid": "value",
            },
        },
    )

    assert response.status_code == 422


def test_chat_logs_final_validated_citations_without_payloads(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    logged_events = []
    sensitive_question = "pregunta privada del usuario"
    sensitive_chunk = "contenido privado del documento"
    sensitive_answer = "respuesta privada [[S2]]"
    results = [
        {
            "source_id": "S1",
            "text": sensitive_chunk,
            "filename": "manual.pdf",
            "page_number": 3,
            "chunk_index": 1,
        },
        {
            "source_id": "S2",
            "text": sensitive_chunk,
            "filename": "manual.pdf",
            "page_number": 8,
            "chunk_index": 2,
        },
    ]

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks_with_metadata",
        lambda question, session_id, n_results=6: results,
    )
    monkeypatch.setattr(
        "app.routers.chat.generate_cited_response",
        lambda question, chunks: CitedAnswer(
            answer=sensitive_answer,
            source_ids=["S2"],
        ),
    )
    monkeypatch.setattr(
        "app.observability.log_event",
        lambda event, **fields: logged_events.append((event, fields)),
    )

    response = client.post("/chat", json={"message": sensitive_question})

    assert response.status_code == 200
    event, fields = logged_events[0]
    serialized = str(fields)
    assert event == "rag_request_completed"
    assert fields["endpoint"] == "/chat"
    assert fields["chunks_retrieved"] == 2
    assert fields["cited_source_ids"] == ["S2"]
    assert fields["cited_pages"] == [8]
    assert sensitive_question not in serialized
    assert sensitive_chunk not in serialized
    assert sensitive_answer not in serialized
