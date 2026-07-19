from pydantic import BaseModel


class Message(BaseModel):
    message: str


class DocumentQuestion(BaseModel):
    message: str
    document_id: str