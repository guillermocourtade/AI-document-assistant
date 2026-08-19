export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
  };
};

export type FastApiValidationError = {
  detail: Array<{
    loc: Array<string | number>;
    msg: string;
    type: string;
  }>;
};

export type UploadDocumentResponse = {
  message: string;
  document_id: string;
  filename: string;
  chunks_saved: number;
  duplicate?: boolean;
};

export type DocumentsResponse = {
  documents: UploadedDocument[];
};

export type ChatRequest = {
  message: string;
};

export type ChatResponse = {
  answer: string;
};

export type DocumentChatRequest = {
  message: string;
  document_id: string;
};

export type DocumentChatResponse = {
  answer: string;
  document_id: string;
};

export type SearchResponse = string[];

export type UploadedDocument = {
  document_id: string;
  filename: string;
  chunks_saved: number;
  uploaded_at?: string;
};

export type ChatMode = "all" | "document";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  documentId?: string;
};
