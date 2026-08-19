import os
import uuid

import chromadb

from app.exceptions.custom_exceptions import (
    DocumentNotFoundError,
    VectorDatabaseError,
)
from app.logger import logger
from app.services.openai_service import generate_embedding


_client = None
_collection = None
_db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")


def configure_vector_db(path: str) -> None:
    global _client, _collection, _db_path

    _db_path = path
    _client = None
    _collection = None


def get_collection():
    global _client, _collection

    if _client is None:
        _client = chromadb.PersistentClient(path=_db_path)

    if _collection is None:
        _collection = _client.get_or_create_collection(
            name="documents"
        )

    return _collection


def find_document_by_hash(file_hash: str) -> str | None:
    try:
        results = get_collection().get(
            where={"file_hash": file_hash},
            limit=1,
        )

    except Exception as exception:
        logger.exception(
            "Error buscando documento por hash."
        )

        raise VectorDatabaseError(
            "No fue posible consultar documentos existentes."
        ) from exception

    metadatas = results.get("metadatas", [])

    if not metadatas:
        return None

    return metadatas[0].get("document_id")


def count_document_chunks(document_id: str) -> int:
    try:
        results = get_collection().get(
            where={"document_id": document_id},
        )

    except Exception as exception:
        logger.exception(
            "Error contando chunks del documento %s.",
            document_id,
        )

        raise VectorDatabaseError(
            "No fue posible consultar documentos existentes."
        ) from exception

    return len(results.get("ids", []))


def list_documents() -> list[dict]:
    try:
        results = get_collection().get(
            include=["metadatas"],
        )

    except Exception as exception:
        logger.exception(
            "Error listando documentos."
        )

        raise VectorDatabaseError(
            "No fue posible listar los documentos."
        ) from exception

    documents_by_id: dict[str, dict] = {}

    for metadata in results.get("metadatas", []):
        document_id = metadata.get("document_id")

        if document_id is None:
            continue

        document = documents_by_id.setdefault(
            document_id,
            {
                "document_id": document_id,
                "filename": metadata.get("filename", "Documento"),
                "chunks_saved": 0,
            },
        )

        document["chunks_saved"] += 1

    return list(documents_by_id.values())


def save_chunks(
    chunks_with_embeddings: list[dict],
    filename: str,
    file_hash: str,
) -> str:
    document_id = str(uuid.uuid4())

    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []

    for index, item in enumerate(chunks_with_embeddings):
        ids.append(str(uuid.uuid4()))
        documents.append(item["text"])
        embeddings.append(item["embedding"])

        metadatas.append(
            {
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "chunk_index": index,
            }
        )

    logger.info(
        "Guardando %d chunks para el documento %s.",
        len(documents),
        document_id,
    )

    try:
        get_collection().add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    except Exception as exception:
        logger.exception(
            "Error guardando chunks en la base vectorial."
        )

        raise VectorDatabaseError(
            "No fue posible guardar los chunks en la base vectorial."
        ) from exception

    logger.info(
        "Documento guardado correctamente. document_id=%s, chunks=%d.",
        document_id,
        len(documents),
    )

    return document_id


def search_similar_chunks(
    question: str,
    n_results: int = 4,
    document_id: str | None = None,
    max_distance: float = 1.2,
) -> list[str]:
    logger.info(
        "Iniciando búsqueda vectorial. "
        "document_id=%s, top_k=%d, max_distance=%.2f.",
        document_id,
        n_results,
        max_distance,
    )

    if document_id is not None and not document_exists(document_id):
        logger.warning(
            "No existe el documento solicitado. document_id=%s.",
            document_id,
        )

        raise DocumentNotFoundError(
            f"No existe un documento con el ID '{document_id}'."
        )

    # Si OpenAI falla, debe conservarse AIServiceError.
    question_embedding = generate_embedding(question)

    query_arguments = {
        "query_embeddings": [question_embedding],
        "n_results": n_results,
        "include": ["documents", "distances"],
    }

    if document_id is not None:
        query_arguments["where"] = {
            "document_id": document_id,
        }

    try:
        results = get_collection().query(**query_arguments)

    except Exception as exception:
        logger.exception(
            "Error consultando la base vectorial. document_id=%s.",
            document_id,
        )

        raise VectorDatabaseError(
            "No fue posible consultar la base vectorial."
        ) from exception

    documents = results.get("documents", [])
    distances = results.get("distances", [])

    if not documents or not distances:
        logger.info(
            "La consulta vectorial no devolvió resultados. "
            "document_id=%s.",
            document_id,
        )

        return []

    retrieved_documents = documents[0]
    retrieved_distances = distances[0]

    relevant_chunks = [
        chunk
        for chunk, distance in zip(
            retrieved_documents,
            retrieved_distances,
        )
        if distance <= max_distance
    ]

    logger.info(
        "Búsqueda terminada. recuperados=%d, relevantes=%d.",
        len(retrieved_documents),
        len(relevant_chunks),
    )

    logger.debug(
        "Distancias recuperadas: %s.",
        retrieved_distances,
    )

    return relevant_chunks


def document_exists(document_id: str) -> bool:
    logger.debug(
        "Verificando existencia del documento %s.",
        document_id,
    )

    try:
        results = get_collection().get(
            where={"document_id": document_id},
            limit=1,
        )

    except Exception as exception:
        logger.exception(
            "Error verificando el documento %s.",
            document_id,
        )

        raise VectorDatabaseError(
            "No fue posible verificar el documento "
            "en la base vectorial."
        ) from exception

    ids = results.get("ids", [])
    exists = bool(ids)

    logger.debug(
        "Resultado de verificación. document_id=%s, exists=%s.",
        document_id,
        exists,
    )

    return exists
