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
  page_count: number;
  duplicate?: boolean;
};

export type UploadProcessingProgress = {
  status: "processing" | "complete" | "failed";
  progress: number;
  phase: string;
  detail: string;
};

export type DocumentsResponse = {
  documents: UploadedDocument[];
};

export type ChatRequest = {
  message: string;
};

export type Source = {
  filename: string;
  page_number: number | null;
};

export type ChatResponse = {
  answer: string;
  sources: Source[];
};

export type DocumentChatRequest = {
  message: string;
  document_id: string;
};

export type DocumentChatResponse = {
  answer: string;
  document_id: string;
  sources: Source[];
};

export type SearchResponse = string[];

export type UploadedDocument = {
  document_id: string;
  filename: string;
  chunks_saved: number;
  page_count?: number;
  uploaded_at?: string;
  created_at?: string;
  expires_at?: string;
};

export type ChatMode = "all" | "document";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  documentId?: string;
  sources?: Source[];
};
