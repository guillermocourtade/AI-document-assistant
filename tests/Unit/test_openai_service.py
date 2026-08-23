import json
from types import SimpleNamespace

from app.services.openai_service import (
    CitedAnswer,
    build_citation_context,
    build_context,
    generate_cited_response,
    generate_embedding,
    generate_response,
)
from app.observability import observe_rag_request


def test_build_context_formats_chunks():
    chunks = [
        "Primer fragmento",
        "Segundo fragmento",
    ]

    context = build_context(chunks)

    assert isinstance(context, str)
    assert "Fragmento 1:\nPrimer fragmento" in context
    assert "Fragmento 2:\nSegundo fragmento" in context


def test_build_citation_context_sends_ids_and_text_without_page_numbers():
    context = build_citation_context(
        [
            {
                "source_id": "S1",
                "text": "El aviso debe darse con anticipación.",
                "filename": "manual.pdf",
                "page_number": 13,
                "chunk_index": 81,
            }
        ]
    )

    assert json.loads(context) == [
        {
            "source_id": "S1",
            "content": "El aviso debe darse con anticipación.",
        }
    ]


def test_generate_cited_response_uses_structured_output(monkeypatch):
    received_data = {}
    parsed = CitedAnswer(
        answer="Debe avisar con 30 días de anticipación [[S1]].",
        source_ids=["S1"],
    )

    def fake_parse(**kwargs):
        received_data.update(kwargs)
        return SimpleNamespace(output_parsed=parsed)

    monkeypatch.setattr(
        "app.services.openai_service.client.responses.parse",
        fake_parse,
    )

    result = generate_cited_response(
        question="¿Con cuánta anticipación?",
        chunks=[{"source_id": "S1", "text": "Debe avisar con 30 días."}],
    )

    assert result == parsed
    assert received_data["text_format"] is CitedAnswer
    assert '"source_id": "S1"' in received_data["input"]
    assert "no escribas números" in received_data["input"]


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


def test_generate_cited_response_without_chunks_does_not_call_openai(
    monkeypatch,
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "OpenAI no debería llamarse cuando chunks está vacío."
        )

    monkeypatch.setattr(
        "app.services.openai_service.client.responses.parse",
        fail_if_called,
    )

    result = generate_cited_response(question="Pregunta", chunks=[])

    assert result == CitedAnswer(
        answer="No se encontró información relevante en los documentos.",
        source_ids=[],
    )


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


def test_generate_cited_response_records_model_usage_and_latency(monkeypatch):
    parsed = CitedAnswer(answer="Respuesta [[S1]].", source_ids=["S1"])
    fake_response = SimpleNamespace(
        output_parsed=parsed,
        model="gpt-4.1-mini-2026-01-01",
        usage=SimpleNamespace(input_tokens=120, output_tokens=30),
    )
    times = iter([5.0, 5.075])

    monkeypatch.setattr(
        "app.services.openai_service.client.responses.parse",
        lambda **kwargs: fake_response,
    )
    monkeypatch.setattr(
        "app.services.openai_service.perf_counter",
        lambda: next(times),
    )
    monkeypatch.setattr(
        "app.observability.log_event",
        lambda event, **fields: None,
    )

    with observe_rag_request("/chat") as observation:
        result = generate_cited_response(
            question="Pregunta",
            chunks=[{"source_id": "S1", "text": "Contenido"}],
        )

        assert result == parsed
        assert observation.openai_generation_latency_ms == 75.0
        assert observation.model == "gpt-4.1-mini-2026-01-01"
        assert observation.input_tokens == 120
        assert observation.output_tokens == 30

