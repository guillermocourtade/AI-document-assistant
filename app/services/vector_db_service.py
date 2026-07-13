import chromadb

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