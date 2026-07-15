from openai import OpenAI
from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_response(question: str, chunks: list[str]):

    context = build_context(chunks)

    prompt = f"""
Eres un asistente experto.

Usa únicamente el siguiente contexto.

{context}

Pregunta:
{question}

Si la respuesta no aparece en el contexto, indícalo claramente.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text

def generate_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding

def build_context(chunks: list[str]) -> str:
    context = "\n\n".join(
        f"Fragmento {i + 1}:\n{chunk}"
        for i, chunk in enumerate(chunks)
    )

    return context