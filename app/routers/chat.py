from fastapi import APIRouter
from app.models.message import Message
from app.services.openai_service import generate_response

router = APIRouter()

@router.post("/chat")
def chat_endpoint(message: Message):
    return {"received": generate_response(message.message)}