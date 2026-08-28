from fastapi import APIRouter, Depends, File, UploadFile

from app.models.message import Message
from app.rate_limit import enforce_expensive_endpoint_rate_limit
from app.session import get_active_session_id

from app.services.document_service import (
    calculate_file_hash,
    validate_pdf,
    extract_pages_from_pdf,
    split_pages,
    generate_embeddings,
)

from app.services.vector_db_service import (
    count_document_chunks,
    find_document_by_hash,
    list_documents,
    save_chunks,
    search_similar_chunks,
)


router = APIRouter()


@router.get("/documents")
def get_documents(session_id: str = Depends(get_active_session_id)):
    return {
        "documents": list_documents(session_id),
    }


@router.post(
    "/upload",
    dependencies=[Depends(enforce_expensive_endpoint_rate_limit)],
)
def upload_document(
    file: UploadFile = File(...),
    session_id: str = Depends(get_active_session_id),
):
    validate_pdf(file)

    file_hash = calculate_file_hash(file)
    existing_document_id = find_document_by_hash(file_hash, session_id)

    if existing_document_id is not None:
        return {
            "message": "El documento ya existía.",
            "document_id": existing_document_id,
            "filename": file.filename,
            "chunks_saved": count_document_chunks(
                existing_document_id,
                session_id,
            ),
            "duplicate": True,
        }

    pages = extract_pages_from_pdf(file)

    chunks = split_pages(pages)

    chunks_with_embeddings = generate_embeddings(chunks)

    document_id = save_chunks(
        chunks_with_embeddings,
        file.filename,
        file_hash,
        session_id,
    )

    return {
        "message": "Documento procesado correctamente.",
        "document_id": document_id,
        "filename": file.filename,
        "chunks_saved": len(chunks),
        "duplicate": False,
    }


@router.post("/search")
def search(
    message: Message,
    session_id: str = Depends(get_active_session_id),
):
    results = search_similar_chunks(message.message, session_id)

    return results
