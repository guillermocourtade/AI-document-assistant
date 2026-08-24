from dotenv import load_dotenv
import os


load_dotenv()


def _positive_int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError:
        raise RuntimeError(
            f"{name} debe ser un entero positivo."
        ) from None

    if value <= 0:
        raise RuntimeError(
            f"{name} debe ser un entero positivo."
        )

    return value

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

PDF_MAX_SIZE_BYTES = _positive_int_from_env(
    "PDF_MAX_SIZE_BYTES",
    10 * 1024 * 1024,
)

PDF_MAX_PAGES = _positive_int_from_env(
    "PDF_MAX_PAGES",
    100,
)
