from fastapi import APIRouter
from app.models.message import Message
from app.services.openai_service import generate_response
from app.services.vector_db_service import search_similar_chunks
from app.models.message import Message, DocumentQuestion

router = APIRouter()

@router.post("/chat")
def chat_endpoint(message: Message):
    chunks = search_similar_chunks(message.message)
    
    answer = generate_response(
        message.message,
        chunks)
    
    return {
        "answer": answer}

@router.post("/chat/document")
def chat_with_document(request: DocumentQuestion):
    question = request.message

    chunks = search_similar_chunks(
        question=question,
        document_id=request.document_id
    )

    answer = generate_response(
        question=question,
        chunks=chunks
    )

    return {
        "answer": answer,
        "document_id": request.document_id
    }