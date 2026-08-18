import { useCallback, useState } from "react";
import { api } from "../api/client";
import { getFriendlyErrorMessage } from "../api/errors";
import type { ChatMessage, ChatMode } from "../types/api";

const createMessage = (
  role: ChatMessage["role"],
  content: string,
  documentId?: string,
): ChatMessage => ({
  id: crypto.randomUUID(),
  role,
  content,
  createdAt: new Date().toISOString(),
  documentId,
});

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isAnswering, setIsAnswering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (message: string, mode: ChatMode, documentId?: string) => {
      const trimmedMessage = message.trim();
      if (!trimmedMessage || isAnswering) {
        return;
      }

      setError(null);
      setIsAnswering(true);

      const userMessage = createMessage(
        "user",
        trimmedMessage,
        mode === "document" ? documentId : undefined,
      );

      setMessages((current) => [...current, userMessage]);

      try {
        const response =
          mode === "document" && documentId
            ? await api.chatDocument({
                message: trimmedMessage,
                document_id: documentId,
              })
            : await api.chat({ message: trimmedMessage });

        setMessages((current) => [
          ...current,
          createMessage(
            "assistant",
            response.answer,
            "document_id" in response ? response.document_id : undefined,
          ),
        ]);
      } catch (requestError) {
        const message = getFriendlyErrorMessage(requestError);
        setError(message);
        setMessages((current) => [
          ...current,
          createMessage("assistant", message, documentId),
        ]);
      } finally {
        setIsAnswering(false);
      }
    },
    [isAnswering],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isAnswering,
    error,
    sendMessage,
    clearMessages,
  };
}
