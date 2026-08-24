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


def _nonnegative_int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError:
        raise RuntimeError(
            f"{name} debe ser un entero no negativo."
        ) from None

    if value < 0:
        raise RuntimeError(
            f"{name} debe ser un entero no negativo."
        )

    return value


def _positive_float_from_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = float(raw_value)
    except ValueError:
        raise RuntimeError(
            f"{name} debe ser un número positivo."
        ) from None

    if value <= 0:
        raise RuntimeError(
            f"{name} debe ser un número positivo."
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

RATE_LIMIT_WINDOW_SECONDS = _positive_float_from_env(
    "RATE_LIMIT_WINDOW_SECONDS",
    60.0,
)

UPLOAD_RATE_LIMIT_REQUESTS = _positive_int_from_env(
    "UPLOAD_RATE_LIMIT_REQUESTS",
    5,
)

CHAT_RATE_LIMIT_REQUESTS = _positive_int_from_env(
    "CHAT_RATE_LIMIT_REQUESTS",
    20,
)

OPENAI_TIMEOUT_SECONDS = _positive_float_from_env(
    "OPENAI_TIMEOUT_SECONDS",
    30.0,
)

OPENAI_MAX_RETRIES = _nonnegative_int_from_env(
    "OPENAI_MAX_RETRIES",
    0,
)

OPENAI_MAX_CONCURRENCY = _positive_int_from_env(
    "OPENAI_MAX_CONCURRENCY",
    4,
)
