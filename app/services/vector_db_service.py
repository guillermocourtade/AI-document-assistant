import chromadb
from app.services.openai_service import generate_embedding

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(
    name="documents"
)

def save_chunks(chunks_with_embeddings):
    for i, item in enumerate(chunks_with_embeddings):

        collection.add(
            ids=[str(i)],
            documents=[item["text"]],
            embeddings=[item["embedding"]]
        )

def search_similar_chunks(question, n_results=3):

    question_embedding = generate_embedding(question)

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=n_results
    )

    return results.get("documents", [[]])[0]

