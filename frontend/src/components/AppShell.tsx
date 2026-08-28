import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/40 to-cyan-50/60 text-slate-950">
      <header className="border-b border-indigo-100 bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-cyan-500 text-white shadow-lg shadow-indigo-200">
              <Sparkles size={20} />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
                RAG Workspace
              </p>
              <h1 className="mt-1 text-2xl font-semibold text-slate-950">
                AI Document Assistant
              </h1>
            </div>
          </div>
          <div className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
            Espacio privado de sesión
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
