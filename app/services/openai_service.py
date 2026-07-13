from openai import OpenAI
from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_response(message:str) -> str:
    response = client.responses.create(
        model = "gpt-5-nano",
        input = message,
    )

    return response.output_text


def generate_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )

    return response.data[0].embedding