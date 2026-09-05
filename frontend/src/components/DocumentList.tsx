import { FileText, RefreshCw } from "lucide-react";
import { EmptyState } from "./EmptyState";
import type { UploadedDocument } from "../types/api";

type DocumentListProps = {
  documents: UploadedDocument[];
  activeDocumentId: string | null;
  isLoaded: boolean;
  onSelectDocument: (documentId: string) => void;
  onRefreshDocuments: () => void;
};

export function DocumentList({
  documents,
  activeDocumentId,
  isLoaded,
  onSelectDocument,
  onRefreshDocuments,
}: DocumentListProps) {
  return (
    <section className="rounded-xl border border-indigo-100 bg-white/95 shadow-soft">
      <div className="flex items-center justify-between border-b border-indigo-100 bg-gradient-to-r from-indigo-50/80 to-cyan-50/60 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">
            Documentos subidos
          </h2>
          <p className="text-xs text-slate-500">Disponibles en este navegador</p>
        </div>
        <button
          type="button"
          onClick={onRefreshDocuments}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-indigo-200 bg-white text-indigo-600 transition hover:border-indigo-300 hover:bg-indigo-50"
          aria-label="Actualizar documentos"
          title="Actualizar documentos"
        >
          <RefreshCw size={16} />
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
            title="Sin documentos todavia"
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
                      ? "border-indigo-400 bg-gradient-to-r from-indigo-50 to-cyan-50 ring-2 ring-indigo-100"
                      : "border-slate-200 bg-white hover:border-indigo-200 hover:bg-indigo-50/40"
                  }`}
                >
                  <span className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-cyan-500 text-white shadow-sm">
                      <FileText size={16} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-slate-950">
                        {document.filename}
                      </span>
                      <span className="mt-1 block text-xs text-slate-500">
                        {document.page_count
                          ? `${document.page_count} páginas · `
                          : ""}
                        {document.chunks_saved} fragmentos procesados
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
