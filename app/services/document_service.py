from fastapi import HTTPException
from pypdf import PdfReader
from io import BytesIO

from app.services.openai_service import generate_embedding


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


def split_text(
    text,
    chunk_size=500,
    overlap=100
):
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunks.append(text[start:end])

        start += chunk_size - overlap

    return chunks


def generate_embeddings(chunks):
    embeddings = []

    for chunk in chunks:
        embedding = generate_embedding(chunk)

        embeddings.append({
            "text": chunk,
            "embedding": embedding
        })

    return embeddings