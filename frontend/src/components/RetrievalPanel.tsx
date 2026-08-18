import { Loader2, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api/client";
import { getFriendlyErrorMessage } from "../api/errors";
import { EmptyState } from "./EmptyState";

export function RetrievalPanel() {
  const [query, setQuery] = useState("");
  const [chunks, setChunks] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await api.search({ message });
      setChunks(response);
    } catch (requestError) {
      setChunks([]);
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">
          Debug retrieval
        </h2>
        <p className="text-xs text-slate-500">
          Vista global de `/search`, sin filtro por documento.
        </p>
      </div>

      <div className="p-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Consulta para recuperar chunks"
            className="h-10 min-w-0 flex-1 rounded-md border border-slate-200 px-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
          />
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-slate-900 text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            aria-label="Buscar chunks"
            title="Buscar chunks"
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Search size={16} />
            )}
          </button>
        </form>

        {error && (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="mt-4">
          {!hasSearched ? (
            <EmptyState
              title="Sin búsqueda de debug"
              description="Consulta retrieval para inspeccionar fragmentos."
            />
          ) : chunks.length === 0 && !isLoading ? (
            <EmptyState
              title="Sin fragmentos relevantes"
              description="La búsqueda no devolvió chunks bajo el umbral actual."
            />
          ) : (
            <div className="space-y-3">
              {chunks.map((chunk, index) => (
                <article
                  key={`${chunk.slice(0, 24)}-${index}`}
                  className="rounded-md border border-slate-200 bg-slate-50 p-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Chunk {index + 1}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
                    {chunk}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
