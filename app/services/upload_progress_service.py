from threading import Lock
from time import monotonic


class UploadProgressStore:
    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self._entries: dict[tuple[str, str], dict] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

    def start(self, session_id: str, upload_id: str) -> None:
        self._set(
            session_id,
            upload_id,
            status="processing",
            progress=0,
            phase="Preparando documento",
            detail="El servidor recibió el archivo.",
        )

    def update(
        self,
        session_id: str,
        upload_id: str,
        *,
        progress: int,
        phase: str,
        detail: str,
    ) -> None:
        self._set(
            session_id,
            upload_id,
            status="processing",
            progress=progress,
            phase=phase,
            detail=detail,
        )

    def complete(self, session_id: str, upload_id: str) -> None:
        self._set(
            session_id,
            upload_id,
            status="complete",
            progress=100,
            phase="Documento listo",
            detail="El documento terminó de procesarse.",
        )

    def fail(self, session_id: str, upload_id: str) -> None:
        self._set(
            session_id,
            upload_id,
            status="failed",
            progress=0,
            phase="Procesamiento interrumpido",
            detail="No se pudo completar el procesamiento del documento.",
        )

    def get(self, session_id: str, upload_id: str) -> dict | None:
        now = monotonic()

        with self._lock:
            self._cleanup(now)
            entry = self._entries.get((session_id, upload_id))
            if entry is None:
                return None

            return {
                key: value
                for key, value in entry.items()
                if key != "updated_at"
            }

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def _set(
        self,
        session_id: str,
        upload_id: str,
        *,
        status: str,
        progress: int,
        phase: str,
        detail: str,
    ) -> None:
        now = monotonic()

        with self._lock:
            self._cleanup(now)
            self._entries[(session_id, upload_id)] = {
                "status": status,
                "progress": min(max(progress, 0), 100),
                "phase": phase,
                "detail": detail,
                "updated_at": now,
            }

    def _cleanup(self, now: float) -> None:
        cutoff = now - self._ttl_seconds
        expired_keys = [
            key
            for key, entry in self._entries.items()
            if entry["updated_at"] <= cutoff
        ]

        for key in expired_keys:
            del self._entries[key]


upload_progress_store = UploadProgressStore()
