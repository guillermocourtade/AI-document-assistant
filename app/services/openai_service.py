from openai import OpenAI
from app.config import OPENAI_API_KEY
from openai import OpenAIError
from app.exceptions.custom_exceptions import AIServiceError

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_response(
    question: str,
    chunks: list[str],
) -> str:
    if not chunks:
        return "No se encontró información relevante en los documentos."

    context = build_context(chunks)

    prompt = f"""
Usa únicamente el contexto proporcionado para responder.
Si la respuesta no aparece en el contexto, indícalo claramente.

Contexto:
{context}

Pregunta:
{question}
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
    except OpenAIError as exception:
        raise AIServiceError(
            "No fue posible generar una respuesta con el modelo."
        ) from exception

    return response.output_text

def generate_embedding(text: str) -> list[float]:
    if not isinstance(text, str):
        raise TypeError(
            "generate_embedding esperaba str, "
            f"pero recibió {type(text).__name__}."
        )

    if not text.strip():
        raise ValueError(
            "No se puede generar un embedding de texto vacío."
        )

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
    except OpenAIError as exception:
        raise AIServiceError(
            "No fue posible generar el embedding."
        ) from exception

    return response.data[0].embedding

def build_context(chunks: list[str]) -> str:
    context = "\n\n".join(
        f"Fragmento {i + 1}:\n{chunk}"
        for i, chunk in enumerate(chunks)
    )

    return context