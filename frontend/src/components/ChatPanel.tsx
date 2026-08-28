import { Bot, Eraser, Loader2, Send, User } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type {
  ChatMessage,
  ChatMode,
  UploadedDocument,
} from "../types/api";

type ChatPanelProps = {
  documents: UploadedDocument[];
  messages: ChatMessage[];
  mode: ChatMode;
  activeDocumentId: string | null;
  isAnswering: boolean;
  error: string | null;
  onModeChange: (mode: ChatMode) => void;
  onDocumentChange: (documentId: string) => void;
  onSendMessage: (message: string) => Promise<void>;
  onClearMessages: () => void;
};

const isLowConfidenceAnswer = (content: string) => {
  const normalized = content.toLowerCase();
  return (
    normalized.includes("no se encontró") ||
    normalized.includes("no encontre") ||
    normalized.includes("no encontré") ||
    normalized.includes("no hay información") ||
    normalized.includes("información relevante")
  );
};

export function ChatPanel({
  documents,
  messages,
  mode,
  activeDocumentId,
  isAnswering,
  error,
  onModeChange,
  onDocumentChange,
  onSendMessage,
  onClearMessages,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");

  const activeDocument = useMemo(() => {
    return documents.find(
      (document) => document.document_id === activeDocumentId,
    );
  }, [activeDocumentId, documents]);

  const canUseDocumentMode = documents.length > 0;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isAnswering) {
      return;
    }

    setDraft("");
    await onSendMessage(message);
  };

  return (
    <section className="flex min-h-[620px] flex-col overflow-hidden rounded-xl border border-indigo-100 bg-white/95 shadow-soft">
      <div className="border-b border-indigo-100 bg-gradient-to-r from-white via-indigo-50/60 to-cyan-50/60 px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">
              Chat asistente
            </h2>
            <p className="text-xs text-slate-500">
              {mode === "document" && activeDocument
                ? `Consultando ${activeDocument.filename}`
                : "Consultando todos los documentos indexados"}
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="grid grid-cols-2 rounded-md border border-slate-200 bg-slate-50 p-1 text-xs font-medium">
              <button
                type="button"
                onClick={() => onModeChange("all")}
                className={`rounded px-3 py-2 transition ${
                  mode === "all"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                Todos
              </button>
              <button
                type="button"
                onClick={() => onModeChange("document")}
                disabled={!canUseDocumentMode}
                className={`rounded px-3 py-2 transition disabled:cursor-not-allowed disabled:opacity-40 ${
                  mode === "document"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                Documento
              </button>
            </div>

            <select
              value={activeDocumentId ?? ""}
              onChange={(event) => onDocumentChange(event.target.value)}
              disabled={!canUseDocumentMode}
              className="h-10 min-w-0 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400 sm:w-60"
              aria-label="Documento activo"
            >
              {documents.length === 0 ? (
                <option value="">Sin documentos</option>
              ) : (
                documents.map((document) => (
                  <option
                    key={document.document_id}
                    value={document.document_id}
                  >
                    {document.filename}
                  </option>
                ))
              )}
            </select>

            <button
              type="button"
              onClick={onClearMessages}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
              aria-label="Limpiar conversación"
              title="Limpiar conversación"
            >
              <Eraser size={16} />
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 text-center">
            <div>
              <p className="text-sm font-semibold text-slate-950">
                Haz una pregunta sobre tus documentos
              </p>
              <p className="mt-1 text-sm text-slate-500">
                El historial vive solo en esta sesión del navegador.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => {
              const isAssistant = message.role === "assistant";
              const isLowConfidence =
                isAssistant && isLowConfidenceAnswer(message.content);

              return (
                <article
                  key={message.id}
                  className={`flex gap-3 ${
                    isAssistant ? "justify-start" : "justify-end"
                  }`}
                >
                  {isAssistant && (
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-900 text-white">
                      <Bot size={16} />
                    </span>
                  )}
                  <div
                    className={`max-w-[85%] rounded-lg border px-4 py-3 text-sm leading-6 ${
                      isAssistant
                        ? isLowConfidence
                          ? "border-amber-200 bg-amber-50 text-amber-900"
                          : "border-slate-200 bg-slate-50 text-slate-800"
                        : "border-indigo-600 bg-gradient-to-br from-indigo-600 to-cyan-600 text-white"
                    }`}
                  >
                    <p className="whitespace-pre-wrap break-words">
                      {message.content}
                    </p>
                    {isAssistant &&
                      message.sources &&
                      message.sources.length > 0 && (
                        <div className="mt-3 border-t border-slate-200 pt-2">
                          <p className="text-xs font-semibold text-slate-700">
                            Fuentes
                          </p>
                          <ul className="mt-1 space-y-1 text-xs text-slate-500">
                            {message.sources.map((source, index) => (
                              <li
                                key={`${source.filename}-${source.page_number ?? "sin-pagina"}-${index}`}
                              >
                                {source.filename}
                                {source.page_number !== null &&
                                  ` · página ${source.page_number}`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                  {!isAssistant && (
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-cyan-500 text-white">
                      <User size={16} />
                    </span>
                  )}
                </article>
              );
            })}

            {isAnswering && (
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <Loader2 size={16} className="animate-spin" />
                Generando respuesta
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="border-t border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 p-4"
      >
        <div className="flex gap-2">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Pregunta algo sobre contratos, políticas o documentos subidos..."
            rows={2}
            className="min-h-12 flex-1 resize-none rounded-md border border-slate-200 bg-white px-3 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
          />
          <button
            type="submit"
            disabled={!draft.trim() || isAnswering}
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-cyan-600 text-white shadow-sm transition hover:from-indigo-700 hover:to-cyan-700 disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300"
            aria-label="Enviar mensaje"
            title="Enviar mensaje"
          >
            {isAnswering ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
