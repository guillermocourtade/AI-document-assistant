import { ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../api/client";
import { getFriendlyErrorMessage } from "../api/errors";
import type { UploadDocumentResponse } from "../types/api";
import { DOCUMENT_TTL_HOURS } from "../config";

type DocumentUploadProps = {
  onUploaded: (response: UploadDocumentResponse) => void;
};

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const uploadFile = async (file: File) => {
    setError(null);
    setSuccess(null);

    if (file.type !== "application/pdf") {
      setError("Selecciona un archivo PDF válido.");
      return;
    }

    setIsUploading(true);
    setProgress(0);

    try {
      const response = await api.uploadDocument(file, setProgress);
      onUploaded(response);
      setProgress(100);
      setSuccess(
        response.duplicate
          ? `${response.filename} ya existía.`
          : `${response.filename} procesado correctamente.`,
      );
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setIsUploading(false);
    }
  };

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      void uploadFile(file);
    }
  };

  return (
    <section className="rounded-xl border border-indigo-100 bg-white/95 shadow-soft">
      <div className="border-b border-indigo-100 bg-gradient-to-r from-indigo-50/80 to-cyan-50/60 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">Subir PDF</h2>
        <p className="text-xs text-slate-500">
          Añade un documento para comenzar a consultar.
        </p>
      </div>

      <div className="p-4">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFiles(event.dataTransfer.files);
          }}
          className={`flex w-full flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center transition ${
            isDragging
              ? "border-cyan-500 bg-cyan-50 ring-4 ring-cyan-100"
              : "border-indigo-200 bg-gradient-to-br from-indigo-50/70 to-cyan-50/60 hover:border-indigo-400"
          }`}
        >
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-cyan-500 text-white shadow-md shadow-indigo-200">
            <UploadCloud size={20} />
          </span>
          <span className="mt-3 text-sm font-semibold text-slate-950">
            Arrastra un PDF o selecciónalo
          </span>
          <span className="mt-1 text-xs text-slate-500">
            Se guardará como documento disponible en esta pestaña.
          </span>
        </button>

        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(event) => handleFiles(event.target.files)}
        />

        <div className="mt-4 flex gap-3 rounded-lg border border-sky-100 bg-sky-50/80 px-3 py-3 text-sky-900">
          <ShieldCheck size={17} className="mt-0.5 shrink-0 text-sky-600" />
          <p className="text-xs leading-5">
            Tus documentos son temporales y solo están disponibles durante
            esta sesión. Se eliminan automáticamente después de{" "}
            {DOCUMENT_TTL_HOURS} horas. No subas información sensible.
          </p>
        </div>

        {isUploading && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Subiendo y procesando</span>
              <span>{progress}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-cyan-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {success && (
          <p className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {success}
          </p>
        )}
      </div>
    </section>
  );
}
