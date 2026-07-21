from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.custom_exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(
        request: Request,
        exception: AppError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "error": {
                    "code": exception.error_code,
                    "message": exception.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "Ocurrió un error interno inesperado.",
                }
            },
        )