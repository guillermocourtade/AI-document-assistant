from fastapi import APIRouter
from app.models.message import Message
from app.services.openai_service import generate_response
from app.services.vector_db_service import search_similar_chunks

router = APIRouter()

@router.post("/chat")
def chat_endpoint(message: Message):
    chunks, metadatas = search_similar_chunks(message.message)
    
    answer = generate_response(
        message.message,
        chunks)
    
    return {
        "answer": answer, 
        "sources": metadatas}
