from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.document_service import validate_pdf, extract_text_from_pdf, split_text, generate_embeddings
from app.services.vector_db_service import save_chunks
from app.models.message import Message
from app.services.vector_db_service import search_similar_chunks

router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    validate_pdf(file)

    text = extract_text_from_pdf(file)

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer texto del PDF."
        )

    chunks = split_text(text)

    chunks_with_embeddings = generate_embeddings(chunks)

    document_id = save_chunks(
        chunks_with_embeddings,
        file.filename
    )

    return {
        "message": "Documento procesado correctamente.",
        "document_id": document_id,
        "filename": file.filename,
        "chunks_saved": len(chunks)
    }

   
@router.post("/search")
def search(message: Message):

    results = search_similar_chunks(message.message)

    return results
