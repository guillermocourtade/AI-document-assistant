class AppError(Exception):
    """Excepción base para errores controlados de la aplicación."""

    status_code: int = 500
    error_code: str = "application_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidDocumentError(AppError):
    """Se produce cuando el archivo recibido no es un PDF válido."""

    status_code = 400
    error_code = "invalid_document"


class DocumentProcessingError(AppError):
    """Se produce cuando no es posible extraer o procesar el PDF."""

    status_code = 422
    error_code = "document_processing_error"


class EmptyDocumentError(AppError):
    """Se produce cuando el PDF no contiene suficiente texto utilizable."""

    status_code = 422
    error_code = "empty_document"


class DocumentNotFoundError(AppError):
    """Se produce cuando no existe un documento con el ID solicitado."""

    status_code = 404
    error_code = "document_not_found"


class VectorDatabaseError(AppError):
    """Se produce cuando falla una operación contra ChromaDB."""

    status_code = 503
    error_code = "vector_database_error"


class AIServiceError(AppError):
    """Se produce cuando falla OpenAI u otro servicio de IA."""

    status_code = 502
    error_code = "ai_service_error"