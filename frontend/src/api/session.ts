export const SESSION_STORAGE_KEY = "ai_document_session_id";

export function getSessionId(): string {
  const existingSessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);

  if (existingSessionId) {
    return existingSessionId;
  }

  const sessionId = crypto.randomUUID();
  sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
}
