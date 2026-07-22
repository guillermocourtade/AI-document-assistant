import uuid

import chromadb

from app.exceptions.custom_exceptions import (
    DocumentNotFoundError,
    VectorDatabaseError,
)
from app.logger import logger
from app.services.openai_service import generate_embedding


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(
    name="documents"
)


def save_chunks(
    chunks_with_embeddings: list[dict],
    filename: str,
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
                "chunk_index": index,
            }
        )

    logger.info(
        "Guardando %d chunks para el documento %s.",
        len(documents),
        document_id,
    )

    try:
        collection.add(
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
        results = collection.query(**query_arguments)

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
        results = collection.get(
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