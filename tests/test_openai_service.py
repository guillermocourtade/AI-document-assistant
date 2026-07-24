from app.services.openai_service import build_context


def test_build_context_formats_chunks():
    chunks = [
        "Primer fragmento",
        "Segundo fragmento",
    ]

    context = build_context(chunks)

    assert isinstance(context, str)
    assert "Fragmento 1:\nPrimer fragmento" in context
    assert "Fragmento 2:\nSegundo fragmento" in context

from app.services.openai_service import (
    build_context,
    generate_response,
)


def test_generate_response_without_chunks_does_not_call_openai(
    monkeypatch,
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "OpenAI no debería llamarse cuando chunks está vacío."
        )

    monkeypatch.setattr(
        "app.services.openai_service.client.responses.create",
        fail_if_called,
    )

    answer = generate_response(
        question="¿Qué dice el documento?",
        chunks=[],
    )

    assert answer == (
        "No se encontró información relevante "
        "en los documentos."
    )

from types import SimpleNamespace

from app.services.openai_service import generate_embedding


def test_generate_embedding_returns_vector(
    monkeypatch,
):
    fake_response = SimpleNamespace(
        data=[
            SimpleNamespace(
                embedding=[0.1, 0.2, 0.3]
            )
        ]
    )

    def fake_create(*args, **kwargs):
        return fake_response

    monkeypatch.setattr(
        "app.services.openai_service.client.embeddings.create",
        fake_create,
    )

    embedding = generate_embedding(
        "Texto de prueba"
    )

    assert embedding == [0.1, 0.2, 0.3]
    assert all(
        isinstance(value, float)
        for value in embedding
    )

