from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, UploadFile

from app.config import PDF_MAX_TOTAL_PAGES
from app.exceptions.custom_exceptions import UploadProgressNotFoundError
from app.models.message import Message
from app.rate_limit import enforce_expensive_endpoint_rate_limit
from app.session import get_active_session_id, get_session_id

from app.services.document_service import (
    calculate_file_hash,
    validate_pdf,
    extract_pages_from_pdf,
    split_pages,
    generate_embeddings,
)

from app.services.vector_db_service import (
    count_document_chunks,
    find_document_by_hash,
    list_documents,
    reserve_session_page_capacity,
    save_chunks,
    search_similar_chunks,
)
from app.services.upload_progress_service import upload_progress_store


router = APIRouter()


@router.get("/documents")
def get_documents(session_id: str = Depends(get_active_session_id)):
    return {
        "documents": list_documents(session_id),
    }


@router.get("/upload-progress/{upload_id}")
def get_upload_progress(
    upload_id: UUID,
    session_id: str = Depends(get_session_id),
):
    progress = upload_progress_store.get(session_id, str(upload_id))
    if progress is None:
        raise UploadProgressNotFoundError(
            "No se encontró progreso para esta carga."
        )

    return progress


@router.post(
    "/upload",
    dependencies=[Depends(enforce_expensive_endpoint_rate_limit)],
)
def upload_document(
    file: UploadFile = File(...),
    upload_id: UUID | None = Header(default=None, alias="X-Upload-ID"),
    session_id: str = Depends(get_active_session_id),
):
    progress_id = str(upload_id) if upload_id is not None else None

    def report(progress: int, phase: str, detail: str) -> None:
        if progress_id is not None:
            upload_progress_store.update(
                session_id,
                progress_id,
                progress=progress,
                phase=phase,
                detail=detail,
            )

    if progress_id is not None:
        upload_progress_store.start(session_id, progress_id)

    try:
        report(3, "Validando PDF", "Comprobando el archivo y sus páginas.")
        page_count = validate_pdf(file)

        report(7, "Validando PDF", f"PDF válido: {page_count} páginas.")
        file_hash = calculate_file_hash(file)
        existing_document_id = find_document_by_hash(file_hash, session_id)

        if existing_document_id is not None:
            if progress_id is not None:
                upload_progress_store.complete(session_id, progress_id)

            return {
                "message": "El documento ya existía.",
                "document_id": existing_document_id,
                "filename": file.filename,
                "chunks_saved": count_document_chunks(
                    existing_document_id,
                    session_id,
                ),
                "page_count": page_count,
                "duplicate": True,
            }

        with reserve_session_page_capacity(
            session_id,
            page_count,
            PDF_MAX_TOTAL_PAGES,
        ):
            report(
                10,
                "Extrayendo texto",
                f"Preparando {page_count} páginas.",
            )
            pages = extract_pages_from_pdf(
                file,
                on_progress=lambda current, total: report(
                    10 + round(20 * current / total),
                    "Extrayendo texto",
                    f"Página {current} de {total}.",
                ),
            )

            report(32, "Creando fragmentos", "Dividiendo el texto en chunks.")
            chunks = split_pages(pages)

            report(
                35,
                "Creando índice",
                f"Preparando {len(chunks)} fragmentos.",
            )
            chunks_with_embeddings = generate_embeddings(
                chunks,
                on_progress=lambda current, total: report(
                    35 + round(55 * current / total),
                    "Creando índice",
                    f"Fragmento {current} de {total}.",
                ),
            )

            report(94, "Guardando documento", "Guardando el índice generado.")
            document_id = save_chunks(
                chunks_with_embeddings,
                file.filename,
                file_hash,
                session_id,
                page_count=page_count,
            )

        if progress_id is not None:
            upload_progress_store.complete(session_id, progress_id)

        return {
            "message": "Documento procesado correctamente.",
            "document_id": document_id,
            "filename": file.filename,
            "chunks_saved": len(chunks),
            "page_count": page_count,
            "duplicate": False,
        }
    except Exception:
        if progress_id is not None:
            upload_progress_store.fail(session_id, progress_id)
        raise


@router.post("/search")
def search(
    message: Message,
    session_id: str = Depends(get_active_session_id),
):
    results = search_similar_chunks(message.message, session_id)

    return results
