import { FileText, Trash2 } from "lucide-react";
import { EmptyState } from "./EmptyState";
import type { UploadedDocument } from "../types/api";

type DocumentListProps = {
  documents: UploadedDocument[];
  activeDocumentId: string | null;
  isLoaded: boolean;
  onSelectDocument: (documentId: string) => void;
  onClearDocuments: () => void;
};

export function DocumentList({
  documents,
  activeDocumentId,
  isLoaded,
  onSelectDocument,
  onClearDocuments,
}: DocumentListProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">
            Documentos de la sesión
          </h2>
          <p className="text-xs text-slate-500">
            Guardados en sessionStorage
          </p>
        </div>
        <button
          type="button"
          onClick={onClearDocuments}
          disabled={documents.length === 0}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Limpiar documentos"
          title="Limpiar documentos"
        >
          <Trash2 size={16} />
        </button>
      </div>

      <div className="p-4">
        {!isLoaded ? (
          <div className="space-y-3">
            <div className="h-14 animate-pulse rounded-md bg-slate-100" />
            <div className="h-14 animate-pulse rounded-md bg-slate-100" />
          </div>
        ) : documents.length === 0 ? (
          <EmptyState
            title="Sin documentos todavía"
            description="Sube un PDF para habilitar el chat por documento."
          />
        ) : (
          <div className="space-y-2">
            {documents.map((document) => {
              const isActive = document.document_id === activeDocumentId;

              return (
                <button
                  type="button"
                  key={document.document_id}
                  onClick={() => onSelectDocument(document.document_id)}
                  className={`w-full rounded-md border px-3 py-3 text-left transition ${
                    isActive
                      ? "border-cyan-500 bg-cyan-50"
                      : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  <span className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-900 text-white">
                      <FileText size={16} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-slate-950">
                        {document.filename}
                      </span>
                      <span className="mt-1 block text-xs text-slate-500">
                        {document.chunks_saved} chunks ·{" "}
                        {document.document_id.slice(0, 8)}
                      </span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
