from pypdf import PdfReader

from app.exceptions.custom_exceptions import (
    DocumentProcessingError,
    EmptyDocumentError,
    InvalidDocumentError,
)
from app.logger import logger
from app.services.openai_service import generate_embedding


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
    chunks: list[str],
) -> list[dict]:
    logger.info(
        "Se inició la generación de embeddings para %d chunks.",
        len(chunks),
    )

    embeddings: list[dict] = []

    try:
        for chunk in chunks:
            embedding = generate_embedding(chunk)

            embeddings.append(
                {
                    "text": chunk,
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
