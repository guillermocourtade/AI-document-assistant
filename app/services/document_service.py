from fastapi import HTTPException
from pypdf import PdfReader
from io import BytesIO

def validate_pdf(file):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )
    

def extract_text_from_pdf(file):
    pdf = PdfReader(BytesIO(file.file.read()))

    text = ""

    for page in pdf.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text

def split_text(text, chunk_size=500):
    chunks = []

    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)

    return chunks