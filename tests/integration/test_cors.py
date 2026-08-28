from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.main import app


def test_cors_middleware_uses_configured_allowed_origins() -> None:
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )

    assert cors_middleware.kwargs == {
        "allow_origins": ALLOWED_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
