from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.exceptions.custom_exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    InvalidDocumentError,
)
from app.services.document_service import (
    extract_pages_from_pdf,
    generate_embeddings,
    split_pages,
    split_text,
    validate_pdf,
)


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, pages):
        self.pages = pages


class FakeUploadFile:
    def __init__(
        self,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> None:
        self.file = BytesIO(content)
        self.content_type = content_type


def build_pdf(page_count: int = 1) -> bytes:
    writer = PdfWriter()

    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_validate_pdf_rejects_wrong_declared_type():
    file = FakeUploadFile(
        build_pdf(),
        content_type="text/plain",
    )

    with pytest.raises(
        InvalidDocumentError,
        match="tipo application/pdf",
    ):
        validate_pdf(file)


def test_validate_pdf_rejects_file_over_configured_size(monkeypatch):
    pdf = build_pdf()
    file = FakeUploadFile(pdf)

    monkeypatch.setattr(
        "app.services.document_service.PDF_MAX_SIZE_BYTES",
        len(pdf) - 1,
    )

    with pytest.raises(
        InvalidDocumentError,
        match="tamaño máximo",
    ):
        validate_pdf(file)


def test_validate_pdf_rejects_spoofed_pdf_signature():
    file = FakeUploadFile(b"not-a-pdf-with-sensitive-content")

    with pytest.raises(
        InvalidDocumentError,
        match="no es un PDF válido",
    ):
        validate_pdf(file)


def test_validate_pdf_rejects_malformed_pdf_with_valid_header():
    file = FakeUploadFile(
        b"%PDF-1.7\nOPENAI_API_KEY=should-never-be-returned"
    )

    with pytest.raises(
        InvalidDocumentError,
        match="no es un PDF válido",
    ) as error:
        validate_pdf(file)

    assert "should-never-be-returned" not in str(error.value)


def test_validate_pdf_rejects_too_many_pages(monkeypatch):
    file = FakeUploadFile(build_pdf(page_count=2))

    monkeypatch.setattr(
        "app.services.document_service.PDF_MAX_PAGES",
        1,
    )

    with pytest.raises(
        InvalidDocumentError,
        match="número máximo de páginas",
    ):
        validate_pdf(file)


def test_validate_pdf_restores_stream_position():
    file = FakeUploadFile(build_pdf())
    file.file.seek(3)

    assert validate_pdf(file) == 1

    assert file.file.tell() == 3


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
    progress_updates = []
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

    assert extract_pages_from_pdf(
        file,
        on_progress=lambda current, total: progress_updates.append(
            (current, total)
        ),
    ) == [
        {
            "text": "Texto suficientemente largo en la primera página.",
            "page_number": 1,
        },
        {
            "text": "Texto de la tercera página.",
            "page_number": 3,
        },
    ]
    assert progress_updates == [(1, 3), (2, 3), (3, 3)]


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
    progress_updates = []

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
        ],
        on_progress=lambda current, total: progress_updates.append(
            (current, total)
        ),
    )

    assert embedded_texts == ["chunk uno", "chunk dos"]
    assert progress_updates == [(1, 2), (2, 2)]
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
