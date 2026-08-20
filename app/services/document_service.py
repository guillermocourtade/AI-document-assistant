import hashlib

from pypdf import PdfReader

from app.exceptions.custom_exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    InvalidDocumentError,
)
from app.logger import logger
from app.services.openai_service import generate_embedding


def calculate_file_hash(file) -> str:
    position = file.file.tell()

    try:
        file.file.seek(0)
        file_hash = hashlib.sha256(file.file.read()).hexdigest()
    finally:
        file.file.seek(position)

    return file_hash


def validate_pdf(file) -> None:
    if file.content_type != "application/pdf":
        logger.warning(
            "Se rechazó un archivo con content_type=%s.",
            file.content_type,
        )

        raise InvalidDocumentError(
            "El archivo debe tener el tipo application/pdf."
        )


def extract_text_from_pdf(file) -> str:
    logger.info(
        "Se inició la extracción de texto del PDF."
    )

    try:
        reader = PdfReader(file.file)

        pages_text: list[str] = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                pages_text.append(page_text)

        text = "\n".join(pages_text).strip()

    except Exception as exception:
        logger.exception(
            "Ocurrió un error al leer o procesar el PDF."
        )

        raise DocumentProcessingError(
            "No fue posible leer o procesar el archivo PDF."
        ) from exception

    logger.info(
        "El PDF contiene %d páginas.",
        len(reader.pages),
    )

    if len(text) < 20:
        logger.warning(
            "El PDF no contiene texto suficiente. Caracteres extraídos=%d.",
            len(text),
        )

        raise EmptyDocumentError(
            "El PDF no contiene texto suficiente para procesarse."
        )

    logger.info(
        "La extracción terminó correctamente. Caracteres extraídos=%d.",
        len(text),
    )

    return text


def split_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError(
            "overlap debe ser menor que chunk_size."
        )

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    logger.info(
        "Se generaron %d chunks con chunk_size=%d y overlap=%d.",
        len(chunks),
        chunk_size,
        overlap,
    )

    return chunks


def generate_embeddings(
    chunks: list[dict],
) -> list[dict]:
    logger.info(
        "Se inició la generación de embeddings para %d chunks.",
        len(chunks),
    )

    embeddings: list[dict] = []

    try:
        for chunk in chunks:
            embedding = generate_embedding(chunk["text"])

            embeddings.append(
                {
                    "text": chunk["text"],
                    "page_number": chunk["page_number"],
                    "embedding": embedding,
                }
            )

    except Exception:
        logger.exception(
            "Ocurrió un error durante la generación de embeddings."
        )
        raise

    logger.info(
        "Se generaron correctamente %d embeddings.",
        len(embeddings),
    )

    return embeddings

def extract_pages_from_pdf(file) -> list[dict]:
    try:
        reader = PdfReader(file.file)

        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                pages.append(
                    {
                        "text": text.strip(),
                        "page_number": page_number,
                    }
                )

    except Exception as exc:
        logger.exception("Error extracting pages from PDF")
        raise DocumentProcessingError() from exc

    total_text = " ".join(page["text"] for page in pages)

    if len(total_text.strip()) < 20:
        raise EmptyDocumentError()

    return pages

def split_pages(
    pages: list[dict],
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[dict]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []

    for page in pages:
        text = page["text"]
        page_number = page["page_number"]

        start = 0

        while start < len(text):
            chunk = text[start:start + chunk_size]

            if chunk.strip():
                chunks.append(
                    {
                        "text": chunk.strip(),
                        "page_number": page_number,
                    }
                )

            start += chunk_size - overlap

    return chunks