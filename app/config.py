from dotenv import load_dotenv
import os


load_dotenv()

APP_NAME = os.getenv(
    "APP_NAME",
    "AI Document Assistant",
)

APP_VERSION = os.getenv(
    "APP_VERSION",
    "0.1.0",
)

APP_ENV = os.getenv(
    "APP_ENV",
    "development",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")