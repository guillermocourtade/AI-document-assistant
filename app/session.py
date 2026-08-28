from uuid import UUID

from fastapi import Depends, Header

from app.exceptions.custom_exceptions import InvalidSessionError
from app.services.vector_db_service import cleanup_expired_documents


def get_session_id(
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> str:
    if x_session_id is None:
        raise InvalidSessionError(
            "Falta el identificador de sesión X-Session-ID."
        )

    try:
        session_id = UUID(x_session_id)
    except (TypeError, ValueError, AttributeError):
        raise InvalidSessionError(
            "El identificador de sesión X-Session-ID no es un UUID válido."
        ) from None

    return str(session_id)


def get_active_session_id(
    session_id: str = Depends(get_session_id),
) -> str:
    cleanup_expired_documents()
    return session_id
