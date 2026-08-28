import os
import uuid
from datetime import datetime, timedelta, timezone

import chromadb

from app.config import DOCUMENT_TTL_HOURS
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
        _collection = _client.get_or_create_collection(name="documents")

    return _collection


def _session_filter(session_id: str) -> dict:
    return {"session_id": session_id}


def _session_document_filter(session_id: str, document_id: str) -> dict:
    return {
        "$and": [
            {"session_id": session_id},
            {"document_id": document_id},
        ]
    }


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def cleanup_expired_documents(now: datetime | None = None) -> int:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    try:
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])

        expired_document_ids = {
            metadata.get("document_id")
            for metadata in metadatas
            if metadata
            and metadata.get("document_id")
            and (expires_at := _parse_timestamp(metadata.get("expires_at")))
            is not None
            and expires_at <= current_time
        }
        expired_chunk_ids = [
            chunk_id
            for chunk_id, metadata in zip(ids, metadatas)
            if metadata
            and metadata.get("document_id") in expired_document_ids
        ]

        if expired_chunk_ids:
            collection.delete(ids=expired_chunk_ids)

    except Exception as exception:
        logger.exception("Error eliminando documentos expirados.")
        raise VectorDatabaseError(
            "No fue posible limpiar los documentos expirados."
        ) from exception

    if expired_document_ids:
        logger.info(
            "Limpieza de retención terminada. documentos_eliminados=%d, "
            "chunks_eliminados=%d.",
            len(expired_document_ids),
            len(expired_chunk_ids),
        )

    return len(expired_document_ids)


def find_document_by_hash(file_hash: str, session_id: str) -> str | None:
    try:
        results = get_collection().get(
            where={
                "$and": [
                    _session_filter(session_id),
                    {"file_hash": file_hash},
                ]
            },
            limit=1,
        )
    except Exception as exception:
        logger.exception("Error buscando documento por hash.")
        raise VectorDatabaseError(
            "No fue posible consultar documentos existentes."
        ) from exception

    metadatas = results.get("metadatas", [])
    if not metadatas:
        return None

    return metadatas[0].get("document_id")


def count_document_chunks(document_id: str, session_id: str) -> int:
    try:
        results = get_collection().get(
            where=_session_document_filter(session_id, document_id),
        )
    except Exception as exception:
        logger.exception("Error contando chunks de un documento.")
        raise VectorDatabaseError(
            "No fue posible consultar documentos existentes."
        ) from exception

    return len(results.get("ids", []))


def list_documents(session_id: str) -> list[dict]:
    try:
        results = get_collection().get(
            where=_session_filter(session_id),
            include=["metadatas"],
        )
    except Exception as exception:
        logger.exception("Error listando documentos.")
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
                "created_at": metadata.get("created_at"),
                "expires_at": metadata.get("expires_at"),
            },
        )
        document["chunks_saved"] += 1

    return list(documents_by_id.values())


def save_chunks(
    chunks_with_embeddings: list[dict],
    filename: str,
    file_hash: str,
    session_id: str,
    created_at: datetime | None = None,
) -> str:
    document_id = str(uuid.uuid4())
    creation_time = created_at or datetime.now(timezone.utc)
    if creation_time.tzinfo is None:
        creation_time = creation_time.replace(tzinfo=timezone.utc)
    creation_time = creation_time.astimezone(timezone.utc)
    expiration_time = creation_time + timedelta(hours=DOCUMENT_TTL_HOURS)
    created_at_value = _utc_timestamp(creation_time)
    expires_at_value = _utc_timestamp(expiration_time)

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
                "session_id": session_id,
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "chunk_index": index,
                "page": item["page_number"],
                "page_number": item["page_number"],
                "created_at": created_at_value,
                "expires_at": expires_at_value,
            }
        )

    logger.info("Guardando %d chunks.", len(documents))

    try:
        get_collection().add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    except Exception as exception:
        logger.exception("Error guardando chunks en la base vectorial.")
        raise VectorDatabaseError(
            "No fue posible guardar los chunks en la base vectorial."
        ) from exception

    logger.info("Documento guardado correctamente. chunks=%d.", len(documents))
    return document_id


def search_similar_chunks(
    question: str,
    session_id: str,
    n_results: int = 6,
    document_id: str | None = None,
    max_distance: float = 1.2,
) -> list[str]:
    logger.info(
        "Iniciando búsqueda vectorial. filtro_documento=%s, top_k=%d, "
        "max_distance=%.2f.",
        document_id is not None,
        n_results,
        max_distance,
    )

    if document_id is not None and not document_exists(document_id, session_id):
        logger.warning("No existe el documento solicitado en la sesión.")
        raise DocumentNotFoundError(
            "No existe un documento disponible con ese ID en esta sesión."
        )

    question_embedding = generate_embedding(question)
    query_arguments = {
        "query_embeddings": [question_embedding],
        "n_results": n_results,
        "include": ["documents", "distances"],
        "where": _session_filter(session_id),
    }
    if document_id is not None:
        query_arguments["where"] = _session_document_filter(
            session_id,
            document_id,
        )

    try:
        results = get_collection().query(**query_arguments)
    except Exception as exception:
        logger.exception("Error consultando la base vectorial.")
        raise VectorDatabaseError(
            "No fue posible consultar la base vectorial."
        ) from exception

    documents = results.get("documents", [])
    distances = results.get("distances", [])
    if not documents or not distances:
        return []

    retrieved_documents = documents[0]
    retrieved_distances = distances[0]
    relevant_chunks = [
        chunk
        for chunk, distance in zip(retrieved_documents, retrieved_distances)
        if distance <= max_distance
    ]
    logger.info(
        "Búsqueda terminada. recuperados=%d, relevantes=%d.",
        len(retrieved_documents),
        len(relevant_chunks),
    )
    logger.debug("Distancias recuperadas: %s.", retrieved_distances)
    return relevant_chunks


def search_similar_chunks_with_metadata(
    question: str,
    session_id: str,
    n_results: int = 6,
    document_id: str | None = None,
    max_distance: float = 1.2,
) -> list[dict]:
    logger.info(
        "Iniciando búsqueda vectorial con metadata. "
        "filtro_documento=%s, top_k=%d, max_distance=%.2f.",
        document_id is not None,
        n_results,
        max_distance,
    )

    if document_id is not None and not document_exists(document_id, session_id):
        logger.warning("No existe el documento solicitado en la sesión.")
        raise DocumentNotFoundError(
            "No existe un documento disponible con ese ID en esta sesión."
        )

    question_embedding = generate_embedding(question)
    query_arguments = {
        "query_embeddings": [question_embedding],
        "n_results": n_results,
        "include": ["documents", "distances", "metadatas"],
        "where": _session_filter(session_id),
    }
    if document_id is not None:
        query_arguments["where"] = _session_document_filter(
            session_id,
            document_id,
        )

    try:
        results = get_collection().query(**query_arguments)
    except Exception as exception:
        logger.exception("Error consultando la base vectorial con metadata.")
        raise VectorDatabaseError(
            "No fue posible consultar la base vectorial."
        ) from exception

    documents = results.get("documents", [])
    distances = results.get("distances", [])
    metadatas = results.get("metadatas", [])
    if not documents or not distances:
        return []

    retrieved_documents = documents[0]
    retrieved_distances = distances[0]
    retrieved_metadatas = metadatas[0] if metadatas else []
    relevant_chunks: list[dict] = []

    for index, (chunk, distance) in enumerate(
        zip(retrieved_documents, retrieved_distances)
    ):
        if distance > max_distance:
            continue

        metadata = (
            retrieved_metadatas[index]
            if index < len(retrieved_metadatas)
            and retrieved_metadatas[index] is not None
            else {}
        )
        page_number = metadata.get("page", metadata.get("page_number"))
        if not isinstance(page_number, int) or isinstance(page_number, bool):
            page_number = None

        relevant_chunks.append(
            {
                "source_id": f"S{len(relevant_chunks) + 1}",
                "text": chunk,
                "filename": metadata.get("filename", "Documento"),
                "page_number": page_number,
                "chunk_index": metadata.get("chunk_index"),
            }
        )

    logger.info(
        "Búsqueda con metadata terminada. recuperados=%d, relevantes=%d.",
        len(retrieved_documents),
        len(relevant_chunks),
    )
    logger.debug(
        "Distancias recuperadas con metadata: %s.",
        retrieved_distances,
    )
    return relevant_chunks


def document_exists(document_id: str, session_id: str) -> bool:
    logger.debug("Verificando existencia de un documento en la sesión.")

    try:
        results = get_collection().get(
            where=_session_document_filter(session_id, document_id),
            limit=1,
        )
    except Exception as exception:
        logger.exception("Error verificando un documento.")
        raise VectorDatabaseError(
            "No fue posible verificar el documento en la base vectorial."
        ) from exception

    exists = bool(results.get("ids", []))
    logger.debug("Resultado de verificación. exists=%s.", exists)
    return exists
