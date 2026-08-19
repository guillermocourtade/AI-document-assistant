import { ApiError, toApiError } from "./errors";
import type {
  ChatRequest,
  ChatResponse,
  DocumentChatRequest,
  DocumentChatResponse,
  DocumentsResponse,
  SearchResponse,
  UploadDocumentResponse,
} from "../types/api";

const API_URL = import.meta.env.VITE_API_URL ?? "";

const buildUrl = (path: string) => {
  return `${API_URL.replace(/\/$/, "")}${path}`;
};

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(
      "La API devolvió una respuesta que no es JSON válido.",
      "invalid_json",
      response.status,
    );
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const body = await parseJson(response);

  if (!response.ok) {
    throw toApiError(body, response.status);
  }

  return body as T;
}

export const api = {
  listDocuments(): Promise<DocumentsResponse> {
    return request<DocumentsResponse>("/documents");
  },

  chat(payload: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  chatDocument(
    payload: DocumentChatRequest,
  ): Promise<DocumentChatResponse> {
    return request<DocumentChatResponse>("/chat/document", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  search(payload: ChatRequest): Promise<SearchResponse> {
    return request<SearchResponse>("/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  uploadDocument(
    file: File,
    onProgress?: (progress: number) => void,
  ): Promise<UploadDocumentResponse> {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", buildUrl("/upload"));

      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable || !onProgress) {
          return;
        }

        onProgress(Math.round((event.loaded / event.total) * 100));
      };

      xhr.onload = () => {
        let body: unknown = null;

        try {
          body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch {
          reject(
            new ApiError(
              "La API devolvió una respuesta que no es JSON válido.",
              "invalid_json",
              xhr.status,
            ),
          );
          return;
        }

        if (xhr.status < 200 || xhr.status >= 300) {
          reject(toApiError(body, xhr.status));
          return;
        }

        resolve(body as UploadDocumentResponse);
      };

      xhr.onerror = () => {
        reject(
          new TypeError(
            "No se pudo conectar con la API durante la subida.",
          ),
        );
      };

      xhr.send(formData);
    });
  },
};
