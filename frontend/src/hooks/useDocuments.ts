import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { UploadedDocument, UploadDocumentResponse } from "../types/api";

export function useDocuments() {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  const refreshDocuments = useCallback(async () => {
    try {
      const response = await api.listDocuments();
      setDocuments(response.documents);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refreshDocuments().catch(() => {
      setDocuments([]);
    });
  }, [refreshDocuments]);

  const addDocument = useCallback((response: UploadDocumentResponse) => {
    setDocuments((current) => {
      const nextDocument: UploadedDocument = {
        document_id: response.document_id,
        filename: response.filename,
        chunks_saved: response.chunks_saved,
        page_count: response.page_count,
        uploaded_at: new Date().toISOString(),
      };

      return [
        nextDocument,
        ...current.filter(
          (document) => document.document_id !== response.document_id,
        ),
      ];
    });
  }, []);

  const byId = useMemo(() => {
    return new Map(
      documents.map((document) => [document.document_id, document]),
    );
  }, [documents]);

  return {
    documents,
    isLoaded,
    addDocument,
    refreshDocuments,
    getDocumentById: (documentId: string) => byId.get(documentId),
  };
}
