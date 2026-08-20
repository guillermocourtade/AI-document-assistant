import pytest

from app.exceptions.custom_exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
)
from app.services.document_service import (
    extract_pages_from_pdf,
    generate_embeddings,
    split_pages,
    split_text,
)


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, pages):
        self.pages = pages


def test_split_text_returns_list_of_strings():
    text = "a" * 1_000

    chunks = split_text(
        text=text,
        chunk_size=500,
        overlap=100,
    )

    assert isinstance(chunks, list)
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_split_text_uses_overlap():
    text = "0123456789"

    chunks = split_text(
        text=text,
        chunk_size=5,
        overlap=2,
    )

    assert chunks == [
        "01234",
        "34567",
        "6789",
        "9",
    ]


def test_split_text_rejects_invalid_overlap():
    with pytest.raises(
        ValueError,
        match="overlap debe ser menor",
    ):
        split_text(
            text="Texto de prueba",
            chunk_size=100,
            overlap=100,
        )


def test_extract_pages_keeps_human_page_numbers(
    monkeypatch,
):
    fake_reader = FakeReader(
        [
            FakePage("Texto suficientemente largo en la primera página."),
            FakePage(None),
            FakePage("Texto de la tercera página."),
        ]
    )

    monkeypatch.setattr(
        "app.services.document_service.PdfReader",
        lambda stream: fake_reader,
    )

    file = type(
        "FakeUploadFile",
        (),
        {"file": object()},
    )()

    assert extract_pages_from_pdf(file) == [
        {
            "text": "Texto suficientemente largo en la primera página.",
            "page_number": 1,
        },
        {
            "text": "Texto de la tercera página.",
            "page_number": 3,
        },
    ]


def test_extract_pages_preserves_processing_error(
    monkeypatch,
):
    def fail_to_read(stream):
        raise RuntimeError("PDF inválido")

    monkeypatch.setattr(
        "app.services.document_service.PdfReader",
        fail_to_read,
    )

    file = type(
        "FakeUploadFile",
        (),
        {"file": object()},
    )()

    with pytest.raises(
        DocumentProcessingError,
        match="No fue posible leer o procesar el archivo PDF",
    ):
        extract_pages_from_pdf(file)


def test_extract_pages_rejects_document_without_enough_text(
    monkeypatch,
):
    fake_reader = FakeReader([FakePage("Texto corto")])

    monkeypatch.setattr(
        "app.services.document_service.PdfReader",
        lambda stream: fake_reader,
    )

    file = type(
        "FakeUploadFile",
        (),
        {"file": object()},
    )()

    with pytest.raises(
        EmptyDocumentError,
        match="no contiene texto suficiente",
    ):
        extract_pages_from_pdf(file)


def test_split_pages_never_crosses_page_boundaries():
    chunks = split_pages(
        pages=[
            {"text": "abcdefgh", "page_number": 1},
            {"text": "12345678", "page_number": 2},
        ],
        chunk_size=5,
        overlap=2,
    )

    assert chunks == [
        {"text": "abcde", "page_number": 1},
        {"text": "defgh", "page_number": 1},
        {"text": "gh", "page_number": 1},
        {"text": "12345", "page_number": 2},
        {"text": "45678", "page_number": 2},
        {"text": "78", "page_number": 2},
    ]


def test_split_pages_rejects_invalid_overlap():
    with pytest.raises(
        ValueError,
        match="overlap debe ser menor",
    ):
        split_pages(
            pages=[],
            chunk_size=100,
            overlap=100,
        )


def test_generate_embeddings_keeps_page_number_and_embeds_once(
    monkeypatch,
):
    embedded_texts = []

    def fake_generate_embedding(text):
        embedded_texts.append(text)
        return [float(len(text))]

    monkeypatch.setattr(
        "app.services.document_service.generate_embedding",
        fake_generate_embedding,
    )

    result = generate_embeddings(
        [
            {"text": "chunk uno", "page_number": 1},
            {"text": "chunk dos", "page_number": 2},
        ]
    )

    assert embedded_texts == ["chunk uno", "chunk dos"]
    assert result == [
        {
            "text": "chunk uno",
            "page_number": 1,
            "embedding": [9.0],
        },
        {
            "text": "chunk dos",
            "page_number": 2,
            "embedding": [9.0],
        },
    ]
