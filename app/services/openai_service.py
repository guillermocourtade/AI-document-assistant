from types import SimpleNamespace

from openai import OpenAI, OpenAIError

from app.config import OPENAI_API_KEY
from app.exceptions.custom_exceptions import AIServiceError
from app.logger import logger


client = OpenAI(api_key=OPENAI_API_KEY)


def generate_response(
    question: str,
    chunks: list[str],
) -> str:
    if not chunks:
        logger.info(
            "No se generó una respuesta porque no se encontraron "
            "chunks relevantes."
        )

        return (
            "No se encontró información relevante "
            "en los documentos."
        )

    logger.info(
        "Se inició la generación de respuesta con %d chunks.",
        len(chunks),
    )

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
        logger.exception(
            "Error generando una respuesta con la API de OpenAI."
        )

        raise AIServiceError(
            "No fue posible generar una respuesta con el modelo."
        ) from exception

    logger.info(
        "La respuesta fue generada correctamente."
    )

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

    logger.debug(
        "Se inició la generación de un embedding. Caracteres=%d.",
        len(text),
    )

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )

    except OpenAIError as exception:
        logger.exception(
            "Error generando el embedding con la API de OpenAI."
        )

        raise AIServiceError(
            "No fue posible generar el embedding."
        ) from exception

    logger.debug(
        "El embedding fue generado correctamente."
    )

    return response.data[0].embedding


def build_context(chunks: list[str]) -> str:
    logger.info(
        "Se enviarán %d chunks al modelo.",
        len(chunks),
    )

    return "\n\n".join(
        f"Fragmento {index + 1}:\n{chunk}"
        for index, chunk in enumerate(chunks)
    )
