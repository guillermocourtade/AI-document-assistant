from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.document_service import validate_pdf

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    validate_pdf(file)
    return {"filename": file.filename, 
            "content_type": file.content_type}