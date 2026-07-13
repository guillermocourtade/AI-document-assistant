from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.document_service import validate_pdf, extract_text_from_pdf, split_text, generate_embeddings

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    validate_pdf(file)
    text = extract_text_from_pdf(file)
    chunks = split_text(text)
    embeddings = generate_embeddings(chunks)
    return {"filename": file.filename, 
            "num_chunks": len(chunks),
            "embeddings_created" : len(embeddings),
            "preview": embeddings[:2]}

