from fastapi import APIRouter

from app.models.message import DocumentQuestion, Message
from app.services.openai_service import generate_response
from app.services.vector_db_service import (
    search_similar_chunks_with_metadata,
)


router = APIRouter()


def _build_sources(results: list[dict]) -> list[dict]:
    sources: list[dict] = []
    seen_sources: set[tuple[str, int | None]] = set()

    for result in results:
        source = {
            "filename": result["filename"],
            "page_number": result["page_number"],
        }
        source_key = (
            source["filename"],
            source["page_number"],
        )

        if source_key in seen_sources:
            continue

        seen_sources.add(source_key)
        sources.append(source)

    return sources


@router.post("/chat")
def chat_endpoint(message: Message):
    results = search_similar_chunks_with_metadata(message.message)
    chunks = [result["text"] for result in results]

    answer = generate_response(
        message.message,
        chunks,
    )

    return {
        "answer": answer,
        "sources": _build_sources(results),
    }


@router.post("/chat/document")
def chat_with_document(request: DocumentQuestion):
    question = request.message

    results = search_similar_chunks_with_metadata(
        question=question,
        document_id=request.document_id,
    )
    chunks = [result["text"] for result in results]

    answer = generate_response(
        question=question,
        chunks=chunks,
    )

    return {
        "answer": answer,
        "document_id": request.document_id,
        "sources": _build_sources(results),
    }
