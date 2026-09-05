import type { ApiErrorBody, FastApiValidationError } from "../types/api";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

const isApiErrorBody = (body: unknown): body is ApiErrorBody => {
  if (!body || typeof body !== "object") {
    return false;
  }

  const maybeError = (body as { error?: unknown }).error;
  return (
    !!maybeError &&
    typeof maybeError === "object" &&
    typeof (maybeError as { code?: unknown }).code === "string" &&
    typeof (maybeError as { message?: unknown }).message === "string"
  );
};

const isValidationError = (body: unknown): body is FastApiValidationError => {
  return (
    !!body &&
    typeof body === "object" &&
    Array.isArray((body as { detail?: unknown }).detail)
  );
};

export const toApiError = (
  body: unknown,
  status: number,
  fallback = "No fue posible completar la solicitud.",
): ApiError => {
  if (isApiErrorBody(body)) {
    return new ApiError(body.error.message, body.error.code, status);
  }

  if (isValidationError(body)) {
    const message =
      body.detail[0]?.msg ?? "La API rechazó los datos enviados.";
    return new ApiError(message, "validation_error", status);
  }

  return new ApiError(fallback, "request_error", status);
};

export const getFriendlyErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    const friendlyMessages: Record<string, string> = {
      invalid_document: error.message,
      document_processing_error: error.message,
      empty_document: error.message,
      document_page_limit_exceeded: error.message,
      rate_limit_exceeded: error.message,
      validation_error: "Revisa los datos enviados e inténtalo de nuevo.",
      document_not_found:
        "El documento ya no está disponible. La lista se actualizó.",
      invalid_session:
        "La sesión del navegador no es válida. Recarga la página para iniciar una nueva.",
      vector_database_error:
        "Los documentos no están disponibles temporalmente. Inténtalo de nuevo.",
      ai_service_error:
        "No fue posible generar una respuesta en este momento.",
      ai_service_timeout:
        "La respuesta tardó demasiado. Inténtalo de nuevo.",
      service_busy:
        "El asistente está ocupado temporalmente. Inténtalo más tarde.",
    };

    return (
      friendlyMessages[error.code] ??
      "No fue posible completar la solicitud. Inténtalo de nuevo."
    );
  }

  if (error instanceof TypeError) {
    return "No se pudo conectar con el servicio. Revisa tu conexión e inténtalo de nuevo.";
  }

  return "Ocurrió un error inesperado.";
};
