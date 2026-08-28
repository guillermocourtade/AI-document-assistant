import re
from time import perf_counter

from fastapi import APIRouter, Depends

from app.models.message import DocumentQuestion, Message
from app.observability import RagObservation, observe_rag_request
from app.rate_limit import enforce_expensive_endpoint_rate_limit
from app.session import get_active_session_id
from app.services.openai_service import CitedAnswer, generate_cited_response
from app.services.vector_db_service import (
    search_similar_chunks_with_metadata,
)


router = APIRouter()

_MODEL_PAGE_CITATION = re.compile(r"\[p\.\s*\d+\]", re.IGNORECASE)
_SOURCE_CITATION = re.compile(r"\[\[\s*(S\d+)\s*\]\]")
_UNKNOWN_MARKER = re.compile(r"\[\[[^\[\]\n]+\]\]")
_FINAL_PAGE_CITATION = re.compile(r"\[p\. (?P<page_number>\d+)\]")


def _build_sources(results: list[dict]) -> list[dict]:
    sources: list[dict] = []
    seen_sources: set[tuple[str, int | None]] = set()

    for result in results:
        source = {
            "filename": result["filename"],
            "page_number": result["page_number"],
        }
        source_key = (
            source["filename"],
            source["page_number"],
        )

        if source_key in seen_sources:
            continue

        seen_sources.add(source_key)
        sources.append(source)

    return sources


def _source_label(result: dict) -> str:
    page_number = result["page_number"]

    if isinstance(page_number, int):
        return f"[p. {page_number}]"

    return "[fuente sin página]"


def _normalize_validated_citations(
    answer: str,
    cited_results: list[dict],
) -> str:
    validated_pages = {
        result["page_number"]
        for result in cited_results
        if isinstance(result["page_number"], int)
        and not isinstance(result["page_number"], bool)
    }

    def normalize_spacing(match: re.Match) -> str:
        page_number = int(match.group("page_number"))

        if page_number not in validated_pages:
            return ""

        citation = match.group(0)
        if match.start() > 0 and not answer[match.start() - 1].isspace():
            return f" {citation}"

        return citation

    answer = _FINAL_PAGE_CITATION.sub(normalize_spacing, answer)

    for page_number in sorted(validated_pages):
        citation = re.escape(f"[p. {page_number}]")
        consecutive_duplicates = re.compile(
            rf"({citation})(?:[ \t]*{citation})+"
        )
        answer = consecutive_duplicates.sub(r"\1", answer)

    return answer


def _map_citations(
    generated: CitedAnswer,
    results: list[dict],
) -> tuple[str, list[dict]]:
    results_by_id = {
        result["source_id"]: result
        for result in results
    }
    declared_ids = set(generated.source_ids)
    used_ids: list[str] = []

    # El modelo nunca es autoridad para los números de página.
    answer = _MODEL_PAGE_CITATION.sub("", generated.answer)

    def replace_marker(match: re.Match) -> str:
        source_id = match.group(1)

        if source_id not in declared_ids or source_id not in results_by_id:
            return ""

        if source_id not in used_ids:
            used_ids.append(source_id)

        return _source_label(results_by_id[source_id])

    answer = _SOURCE_CITATION.sub(replace_marker, answer)
    answer = _UNKNOWN_MARKER.sub("", answer)

    # Si la salida estructurada declara una fuente válida pero omite su
    # marcador, se conserva la cita al final sin aceptar IDs desconocidos.
    for source_id in generated.source_ids:
        if source_id not in results_by_id or source_id in used_ids:
            continue

        used_ids.append(source_id)
        answer = f"{answer.rstrip()} {_source_label(results_by_id[source_id])}"

    cited_results = [results_by_id[source_id] for source_id in used_ids]
    answer = _normalize_validated_citations(answer, cited_results)
    answer = re.sub(r"[ \t]+([.,;:!?])", r"\1", answer)
    answer = re.sub(r"[ \t]{2,}", " ", answer).strip()

    return answer, cited_results


def _answer_question(question: str, results: list[dict]) -> tuple[str, list[dict]]:
    generated = generate_cited_response(
        question=question,
        chunks=results,
    )

    return _map_citations(generated, results)


def _run_rag(
    *,
    question: str,
    endpoint: str,
    session_id: str,
    document_id: str | None = None,
) -> tuple[str, list[dict]]:
    with observe_rag_request(endpoint) as observation:
        results = _retrieve_chunks(
            question=question,
            session_id=session_id,
            document_id=document_id,
            observation=observation,
        )
        answer, cited_results = _answer_question(question, results)
        observation.cited_source_ids = [
            result["source_id"] for result in cited_results
        ]
        observation.cited_pages = list(
            dict.fromkeys(
                result["page_number"]
                for result in cited_results
                if isinstance(result["page_number"], int)
                and not isinstance(result["page_number"], bool)
            )
        )

        return answer, cited_results


def _retrieve_chunks(
    *,
    question: str,
    session_id: str,
    document_id: str | None,
    observation: RagObservation,
) -> list[dict]:
    started_at = perf_counter()

    try:
        if document_id is None:
            results = search_similar_chunks_with_metadata(
                question,
                session_id,
            )
        else:
            results = search_similar_chunks_with_metadata(
                question=question,
                session_id=session_id,
                document_id=document_id,
            )
    finally:
        observation.retrieval_latency_ms = round(
            (perf_counter() - started_at) * 1000,
            3,
        )

    observation.chunks_retrieved = len(results)
    return results


@router.post(
    "/chat",
    dependencies=[Depends(enforce_expensive_endpoint_rate_limit)],
)
def chat_endpoint(
    message: Message,
    session_id: str = Depends(get_active_session_id),
):
    answer, cited_results = _run_rag(
        question=message.message,
        endpoint="/chat",
        session_id=session_id,
    )

    return {
        "answer": answer,
        "sources": _build_sources(cited_results),
    }


@router.post(
    "/chat/document",
    dependencies=[Depends(enforce_expensive_endpoint_rate_limit)],
)
def chat_with_document(
    request: DocumentQuestion,
    session_id: str = Depends(get_active_session_id),
):
    question = request.message
    answer, cited_results = _run_rag(
        question=question,
        endpoint="/chat/document",
        session_id=session_id,
        document_id=request.document_id,
    )

    return {
        "answer": answer,
        "document_id": request.document_id,
        "sources": _build_sources(cited_results),
    }
