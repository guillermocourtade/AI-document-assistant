from dotenv import load_dotenv
import os

load_dotenv()  # Busca automáticamente un archivo .env en el directorio actual y hacia arriba
APP_NAME = os.getenv("APP_NAME")
APP_VERSION= os.getenv("APP_VERSION")
APP_ENV= os.getenv("APP_ENV")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")