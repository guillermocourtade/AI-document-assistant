from app.services.upload_progress_service import UploadProgressStore


def test_upload_progress_store_tracks_lifecycle_and_clamps_percentage():
    store = UploadProgressStore()

    store.start("session-a", "upload-a")
    assert store.get("session-a", "upload-a") == {
        "status": "processing",
        "progress": 0,
        "phase": "Preparando documento",
        "detail": "El servidor recibió el archivo.",
    }

    store.update(
        "session-a",
        "upload-a",
        progress=140,
        phase="Creando índice",
        detail="Fragmento 4 de 4.",
    )
    assert store.get("session-a", "upload-a")["progress"] == 100

    store.complete("session-a", "upload-a")
    assert store.get("session-a", "upload-a")["status"] == "complete"


def test_upload_progress_store_is_scoped_to_session():
    store = UploadProgressStore()
    store.start("session-a", "same-upload")

    assert store.get("session-b", "same-upload") is None
