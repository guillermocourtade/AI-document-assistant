from typing import Any

from fastapi.testclient import TestClient


def test_chat_endpoint_returns_generated_answer(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """
    Verifica el flujo exitoso de POST /chat sin llamar
    realmente a ChromaDB ni a OpenAI.
    """

    received_data: dict[str, object] = {}

    def fake_search_similar_chunks(
        question: str,
        n_results: int = 3,
    ) -> list[str]:
        received_data["search_question"] = question
        received_data["n_results"] = n_results

        return [
            "Python fue creado por Guido van Rossum.",
            "La primera versión pública apareció en 1991.",
        ]

    def fake_generate_response(
        question: str,
        chunks: list[str],
    ) -> str:
        received_data["generation_question"] = question
        received_data["generation_chunks"] = chunks

        return "Respuesta simulada."

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks",
        fake_search_similar_chunks,
    )

    monkeypatch.setattr(
        "app.routers.chat.generate_response",
        fake_generate_response,
    )

    request_body = {
        "message": "¿Quién creó Python?",
    }

    response = client.post(
        "/chat",
        json=request_body,
    )

    assert response.status_code == 300
    assert response.json() == {
        "answer": "Respuesta simulada.",
    }

    assert received_data["search_question"] == "¿Quién creó Python?"
    assert received_data["generation_question"] == "¿Quién creó Python?"

    assert received_data["generation_chunks"] == [
        "Python fue creado por Guido van Rossum.",
        "La primera versión pública apareció en 1991.",
    ]


def test_chat_endpoint_returns_fallback_when_no_chunks_are_found(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """
    Verifica el flujo cuando el retrieval no encuentra
    fragmentos relevantes.
    """

    def fake_search_similar_chunks(
        question: str,
        n_results: int = 3,
    ) -> list[str]:
        return []

    def fake_generate_response(
        question: str,
        chunks: list[str],
    ) -> str:
        assert chunks == []

        return "No se encontró información relevante en los documentos."

    monkeypatch.setattr(
        "app.routers.chat.search_similar_chunks",
        fake_search_similar_chunks,
    )

    monkeypatch.setattr(
        "app.routers.chat.generate_response",
        fake_generate_response,
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