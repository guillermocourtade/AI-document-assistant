import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { UploadedDocument, UploadDocumentResponse } from "../types/api";

const STORAGE_KEY = "ai-document-assistant.documents";

const readDocuments = (): UploadedDocument[] => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

export function useDocuments() {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadDocuments() {
      const sessionDocuments = readDocuments();

      try {
        const response = await api.listDocuments();

        if (!isMounted) {
          return;
        }

        const sessionById = new Map(
          sessionDocuments.map((document) => [
            document.document_id,
            document,
          ]),
        );

        setDocuments(
          response.documents.map((document) => ({
            ...document,
            uploaded_at: sessionById.get(document.document_id)?.uploaded_at,
          })),
        );
      } catch {
        if (isMounted) {
          setDocuments(sessionDocuments);
        }
      } finally {
        if (isMounted) {
          setIsLoaded(true);
        }
      }
    }

    void loadDocuments();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!isLoaded) {
      return;
    }

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(documents));
  }, [documents, isLoaded]);

  const addDocument = useCallback((response: UploadDocumentResponse) => {
    setDocuments((current) => {
      const nextDocument: UploadedDocument = {
        document_id: response.document_id,
        filename: response.filename,
        chunks_saved: response.chunks_saved,
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

  const clearDocuments = useCallback(() => {
    setDocuments([]);
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
    clearDocuments,
    getDocumentById: (documentId: string) => byId.get(documentId),
  };
}
