from fastapi import HTTPException
from pypdf import PdfReader
from io import BytesIO
from app.services.openai_service import generate_embedding
from pypdf import PdfReader
from app.exceptions.custom_exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    InvalidDocumentError,
)


def validate_pdf(file) -> None:
    if file.content_type != "application/pdf":
        raise InvalidDocumentError(
            "El archivo debe tener el tipo application/pdf."
        )


def extract_text_from_pdf(file) -> str:
    try:
        reader = PdfReader(file.file)

        pages_text: list[str] = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                pages_text.append(page_text)

        text = "\n".join(pages_text).strip()

    except EmptyDocumentError:
        raise
    except Exception as exception:
        raise DocumentProcessingError(
            "No fue posible leer o procesar el archivo PDF."
        ) from exception

    if len(text) < 20:
        raise EmptyDocumentError(
            "El PDF no contiene texto suficiente para procesarse."
        )

    return text

def split_text(
    text,
    chunk_size=500,
    overlap=100
):
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunks.append(text[start:end])

        start += chunk_size - overlap

    return chunks


def generate_embeddings(chunks):
    embeddings = []

    for chunk in chunks:
        embedding = generate_embedding(chunk)

        embeddings.append({
            "text": chunk,
            "embedding": embedding
        })

    return embeddings