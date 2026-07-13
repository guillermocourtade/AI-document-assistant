from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.document_service import validate_pdf, extract_text_from_pdf, split_text, generate_embeddings
from app.services.vector_db_service import save_chunks

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    validate_pdf(file)
    text = extract_text_from_pdf(file)
    chunks = split_text(text)
    embeddings = generate_embeddings(chunks)
    save_chunks(embeddings)
    return {"filename": file.filename, 
            "text": text,
            "num_chunks": len(chunks),
            "embeddings_created" : len(embeddings),
            "preview": embeddings[:2]}

