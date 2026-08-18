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
    return error.message;
  }

  if (error instanceof TypeError) {
    return "No se pudo conectar con la API. Revisa que el backend esté levantado y que CORS permita el origen del frontend.";
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Ocurrió un error inesperado.";
};
