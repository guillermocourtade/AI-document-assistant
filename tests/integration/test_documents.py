import hashlib
from datetime import datetime
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from app.services.vector_db_service import get_collection


def build_two_page_pdf() -> bytes:
    writer = PdfWriter()

    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)

    for text in (
        "Contenido suficientemente largo de la pagina uno.",
        "Contenido suficientemente largo de la pagina dos.",
    ):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_reference}
                )
            }
        )

        content = DecodedStreamObject()
        content.set_data(
            f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(content)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()


def test_upload_persists_page_aware_metadata(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_service.generate_embedding",
        lambda text: [float(len(text)), 1.0],
    )

    pdf_bytes = build_two_page_pdf()
    filename = "page-aware.pdf"

    response = client.post(
        "/upload",
        files={
            "file": (
                filename,
                pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    response_body = response.json()
    document_id = response_body["document_id"]

    assert response_body == {
        "message": "Documento procesado correctamente.",
        "document_id": document_id,
        "filename": filename,
        "chunks_saved": 2,
        "duplicate": False,
    }

    stored = get_collection().get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )

    assert len(stored["ids"]) == 2
    assert set(stored["documents"]) == {
        "Contenido suficientemente largo de la pagina uno.",
        "Contenido suficientemente largo de la pagina dos.",
    }

    metadatas = stored["metadatas"]

    assert {metadata["page_number"] for metadata in metadatas} == {1, 2}
    assert {metadata["page"] for metadata in metadatas} == {1, 2}
    assert {metadata["session_id"] for metadata in metadatas} == {
        "11111111-1111-4111-8111-111111111111"
    }
    assert {metadata["document_id"] for metadata in metadatas} == {
        document_id
    }
    assert {metadata["filename"] for metadata in metadatas} == {filename}
    assert {metadata["file_hash"] for metadata in metadatas} == {
        hashlib.sha256(pdf_bytes).hexdigest()
    }
    assert {metadata["chunk_index"] for metadata in metadatas} == {0, 1}
    created_at_values = {
        datetime.fromisoformat(metadata["created_at"])
        for metadata in metadatas
    }
    expires_at_values = {
        datetime.fromisoformat(metadata["expires_at"])
        for metadata in metadatas
    }
    assert len(created_at_values) == 1
    assert len(expires_at_values) == 1
    assert expires_at_values.pop() > created_at_values.pop()


def test_upload_rejects_spoofed_pdf_with_safe_error(
    client: TestClient,
) -> None:
    sensitive_content = b"OPENAI_API_KEY=must-not-leak"

    response = client.post(
        "/upload",
        files={
            "file": (
                "spoofed.pdf",
                sensitive_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_document",
            "message": "El archivo no es un PDF válido.",
        }
    }
    assert "must-not-leak" not in response.text
    assert "Traceback" not in response.text


def test_upload_rejects_pdf_over_configured_size(
    client: TestClient,
    monkeypatch,
) -> None:
    pdf_bytes = build_two_page_pdf()
    monkeypatch.setattr(
        "app.services.document_service.PDF_MAX_SIZE_BYTES",
        len(pdf_bytes) - 1,
    )

    response = client.post(
        "/upload",
        files={"file": ("large.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_document",
        "message": "El archivo PDF excede el tamaño máximo permitido.",
    }


def test_upload_rejects_pdf_over_configured_page_limit(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_service.PDF_MAX_PAGES",
        1,
    )

    response = client.post(
        "/upload",
        files={
            "file": (
                "too-many-pages.pdf",
                build_two_page_pdf(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_document",
        "message": (
            "El archivo PDF excede el número máximo de páginas permitido."
        ),
    }
