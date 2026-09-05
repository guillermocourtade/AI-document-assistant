export const SESSION_STORAGE_KEY = "ai_document_session_id";

export function getSessionId(): string {
  const existingSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

  if (existingSessionId) {
    return existingSessionId;
  }

  const previousSessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (previousSessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, previousSessionId);
    return previousSessionId;
  }

  const sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
}
