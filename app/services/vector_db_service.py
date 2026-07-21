import uuid
import chromadb
from app.services.openai_service import generate_embedding
from app.exceptions.custom_exceptions import VectorDatabaseError
from app.exceptions.custom_exceptions import (
    DocumentNotFoundError,
    VectorDatabaseError,
)


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(
    name="documents"
)


def save_chunks(
    chunks_with_embeddings: list[dict],
    filename: str
) -> str:
    document_id = str(uuid.uuid4())

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for index, item in enumerate(chunks_with_embeddings):
        ids.append(str(uuid.uuid4()))
        documents.append(item["text"])
        embeddings.append(item["embedding"])

        metadatas.append({
            "document_id": document_id,
            "filename": filename,
            "chunk_index": index
        })

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return document_id

def search_similar_chunks(
    question: str,
    n_results: int = 4,
    document_id: str | None = None,
    max_distance: float = 1.2,
) -> list[str]:
    if document_id is not None and not document_exists(document_id):
        raise DocumentNotFoundError(
            f"No existe un documento con el ID '{document_id}'."
        )

    try:
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

        results = collection.query(**query_arguments)

    except DocumentNotFoundError:
        raise
    except Exception as exception:
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
        for chunk, distance in zip(
            retrieved_documents,
            retrieved_distances,
        )
        if distance <= max_distance
    ]

    return relevant_chunks

def document_exists(document_id: str) -> bool:
    try:
        results = collection.get(
            where={"document_id": document_id},
            limit=1,
        )
    except Exception as exception:
        raise VectorDatabaseError(
            "No fue posible verificar el documento en la base vectorial."
        ) from exception

    ids = results.get("ids", [])

    return bool(ids)