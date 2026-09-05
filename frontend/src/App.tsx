import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { ChatPanel } from "./components/ChatPanel";
import { DocumentList } from "./components/DocumentList";
import { DocumentUpload } from "./components/DocumentUpload";
import { RetrievalPanel } from "./components/RetrievalPanel";
import { useChat } from "./hooks/useChat";
import { useDocuments } from "./hooks/useDocuments";
import type { ChatMode } from "./types/api";

export default function App() {
  const {
    documents,
    isLoaded,
    addDocument,
    refreshDocuments,
  } = useDocuments();
  const {
    messages,
    isAnswering,
    error,
    sendMessage,
    clearMessages,
  } = useChat();
  const [mode, setMode] = useState<ChatMode>("all");
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    null,
  );
  const usedPages = documents.reduce(
    (total, document) => total + (document.page_count ?? 0),
    0,
  );

  useEffect(() => {
    if (documents.length === 0) {
      setActiveDocumentId(null);
      setMode("all");
      return;
    }

    const activeStillExists = documents.some(
      (document) => document.document_id === activeDocumentId,
    );

    if (!activeStillExists) {
      setActiveDocumentId(documents[0].document_id);
    }
  }, [activeDocumentId, documents]);

  const handleModeChange = (nextMode: ChatMode) => {
    if (nextMode === "document" && !activeDocumentId) {
      return;
    }

    setMode(nextMode);
  };

  const handleSendMessage = async (message: string) => {
    const result = await sendMessage(
      message,
      mode,
      activeDocumentId ?? undefined,
    );

    if (result === "document_not_found") {
      await refreshDocuments().catch(() => undefined);
    }
  };

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="space-y-6">
          <DocumentUpload
            onUploaded={addDocument}
            usedPages={usedPages}
          />
          <DocumentList
            documents={documents}
            activeDocumentId={activeDocumentId}
            isLoaded={isLoaded}
            onSelectDocument={(documentId) => {
              setActiveDocumentId(documentId);
              setMode("document");
            }}
            onRefreshDocuments={() => {
              void refreshDocuments().catch(() => undefined);
            }}
          />
          <RetrievalPanel />
        </aside>

        <ChatPanel
          documents={documents}
          messages={messages}
          mode={mode}
          activeDocumentId={activeDocumentId}
          isAnswering={isAnswering}
          error={error}
          onModeChange={handleModeChange}
          onDocumentChange={(documentId) => {
            setActiveDocumentId(documentId);
            setMode("document");
          }}
          onSendMessage={handleSendMessage}
          onClearMessages={clearMessages}
        />
      </div>
    </AppShell>
  );
}
