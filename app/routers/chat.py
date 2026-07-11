from fastapi import APIRouter
from models.message import Message
from services.openai_service import generate_response

router = APIRouter()

@router.post("/chat")
def chat_endpoint(message: Message):
    return {"received": generate_response(message.message)}