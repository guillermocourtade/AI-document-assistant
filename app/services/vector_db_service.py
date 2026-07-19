import uuid

import chromadb

from app.services.openai_service import generate_embedding


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
    document_id: str | None = None,
    n_results: int = 5,
    max_distance: float = 1.5
) -> list[str]:
    question_embedding = generate_embedding(question)

    query_arguments = {
        "query_embeddings": [question_embedding],
        "n_results": n_results
    }

    if document_id is not None:
        query_arguments["where"] = {
            "document_id": document_id
        }

    results = collection.query(**query_arguments)

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]

    relevant_documents = []

    for document, distance in zip(documents, distances):
        if distance <= max_distance:
            relevant_documents.append(document)

    return relevant_documents