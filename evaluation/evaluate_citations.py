from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

from app.routers.chat import _build_sources, _map_citations
from app.services.openai_service import CitedAnswer, generate_cited_response
from app.services.vector_db_service import search_similar_chunks_with_metadata
from evaluation.evaluate_retrieval import (
    CHUNK_SIZE,
    DEFAULT_GROUND_TRUTH_PATH,
    DEFAULT_PDF_PATH,
    MAX_DISTANCE,
    N_RESULTS,
    OVERLAP,
    BenchmarkQuestion,
    close_isolated_vector_db,
    configure_vector_db,
    evidence_hit_at_k,
    ingest_benchmark_pdf,
    parse_ground_truth,
)


EVALUATION_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_PATH = EVALUATION_DIR / "results" / "citation_results.json"
GENERATION_MODEL = "gpt-4.1-mini"

RetrievalFunction = Callable[..., list[dict]]
GenerationFunction = Callable[[str, list[dict]], CitedAnswer]


def extract_cited_pages(sources: Iterable[dict]) -> list[int]:
    pages: list[int] = []

    for source in sources:
        page_number = source.get("page_number")
        if (
            not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number in pages
        ):
            continue
        pages.append(page_number)

    return pages


def _rank_retrieved_results(retrieved: list[dict]) -> list[dict]:
    return [
        {
            "rank": rank,
            "source_id": item.get("source_id"),
            "text": item.get("text", ""),
            "filename": item.get("filename"),
            "page_number": item.get("page_number"),
            "chunk_index": item.get("chunk_index"),
        }
        for rank, item in enumerate(retrieved, start=1)
    ]


def _failure_reason(
    *,
    citation_hit: bool,
    cited_pages: list[int],
    retrieval_expected_page_hit: bool,
    retrieval_evidence_hit: bool,
    generation_error: dict | None,
) -> str | None:
    if citation_hit:
        return None
    if generation_error is not None:
        return "generation_error"
    if retrieval_evidence_hit and cited_pages:
        return "llm_cited_other_source"
    if retrieval_evidence_hit:
        return "llm_no_valid_citation"
    if retrieval_expected_page_hit:
        return "retrieval_missing_exact_evidence"
    return "retrieval_miss"


def evaluate_citation_questions(
    questions: Iterable[BenchmarkQuestion],
    document_id: str,
    *,
    retrieval_function: RetrievalFunction = search_similar_chunks_with_metadata,
    generation_function: GenerationFunction = generate_cited_response,
    n_results: int = N_RESULTS,
    max_distance: float = MAX_DISTANCE,
    progress_function: Callable[[str], None] | None = print,
) -> list[dict]:
    results: list[dict] = []

    for question in questions:
        if progress_function is not None:
            progress_function(f"{question.question_id}: retrieval + generation")

        retrieved = retrieval_function(
            question=question.question,
            n_results=n_results,
            document_id=document_id,
            max_distance=max_distance,
        )
        retrieved_pages = [item.get("page_number") for item in retrieved]
        retrieval_expected_page_hit = question.expected_page in retrieved_pages
        retrieval_evidence_hit = evidence_hit_at_k(
            question.evidence,
            retrieved,
            k=max(1, len(retrieved)),
        )

        model_answer: str | None = None
        model_source_ids: list[str] = []
        final_answer: str | None = None
        validated_source_ids: list[str] = []
        sources: list[dict] = []
        generation_error: dict | None = None

        try:
            generated = generation_function(question.question, retrieved)
            model_answer = generated.answer
            model_source_ids = generated.source_ids
            final_answer, cited_results = _map_citations(generated, retrieved)
            validated_source_ids = [
                item["source_id"] for item in cited_results
            ]
            sources = _build_sources(cited_results)
        except Exception as exception:
            generation_error = {
                "type": type(exception).__name__,
                "message": str(exception),
            }

        cited_pages = extract_cited_pages(sources)
        citation_hit = question.expected_page in cited_pages
        failure_reason = _failure_reason(
            citation_hit=citation_hit,
            cited_pages=cited_pages,
            retrieval_expected_page_hit=retrieval_expected_page_hit,
            retrieval_evidence_hit=retrieval_evidence_hit,
            generation_error=generation_error,
        )

        result = asdict(question)
        result.update(
            {
                "retrieved_pages": retrieved_pages,
                "retrieved_results": _rank_retrieved_results(retrieved),
                "retrieval_expected_page_hit": retrieval_expected_page_hit,
                "retrieval_evidence_hit": retrieval_evidence_hit,
                "model_answer": model_answer,
                "model_source_ids": model_source_ids,
                "answer": final_answer,
                "validated_source_ids": validated_source_ids,
                "sources": sources,
                "cited_pages": cited_pages,
                "citation_hit": citation_hit,
                "failure_reason": failure_reason,
                "retrieval_evidence_but_wrong_citation": (
                    failure_reason == "llm_cited_other_source"
                ),
                "generation_error": generation_error,
            }
        )
        results.append(result)

    return results


def calculate_citation_metrics(results: Iterable[dict]) -> dict:
    result_list = list(results)
    total = len(result_list)
    hits = sum(bool(result["citation_hit"]) for result in result_list)

    return {
        "questions": total,
        "citation_hits": hits,
        "citation_misses": total - hits,
        "citation_hit_rate": hits / total if total else 0.0,
        "citation_hit_percentage": (hits / total * 100.0) if total else 0.0,
        "retrieval_expected_page_hits": sum(
            bool(result["retrieval_expected_page_hit"])
            for result in result_list
        ),
        "retrieval_evidence_hits": sum(
            bool(result["retrieval_evidence_hit"])
            for result in result_list
        ),
        "retrieval_evidence_but_wrong_citation": sum(
            bool(result["retrieval_evidence_but_wrong_citation"])
            for result in result_list
        ),
        "retrieval_evidence_but_no_citation": sum(
            result["failure_reason"] == "llm_no_valid_citation"
            for result in result_list
        ),
        "generation_errors": sum(
            result["generation_error"] is not None
            for result in result_list
        ),
        "failed_questions": [
            result["question_id"]
            for result in result_list
            if not result["citation_hit"]
        ],
    }


def _failure_summary(result: dict) -> dict:
    return {
        "question_id": result["question_id"],
        "question": result["question"],
        "expected_page": result["expected_page"],
        "cited_pages": result["cited_pages"],
        "retrieved_pages": result["retrieved_pages"],
        "retrieval_evidence_hit": result["retrieval_evidence_hit"],
        "failure_reason": result["failure_reason"],
    }


def build_citation_report(
    results: list[dict],
    *,
    pdf_path: Path,
    ground_truth_path: Path,
    file_hash: str,
    chunks_saved: int,
) -> dict:
    failures = [
        _failure_summary(result)
        for result in results
        if not result["citation_hit"]
    ]

    return {
        "evaluation": "rag_citation_end_to_end",
        "configuration": {
            "questions": len(results),
            "generation_model": GENERATION_MODEL,
            "generation_function": (
                "app.services.openai_service.generate_cited_response"
            ),
            "retrieval_function": (
                "app.services.vector_db_service."
                "search_similar_chunks_with_metadata"
            ),
            "citation_mapper": "app.routers.chat._map_citations",
            "n_results": N_RESULTS,
            "max_distance": MAX_DISTANCE,
            "chunk_size": CHUNK_SIZE,
            "overlap": OVERLAP,
            "vector_database_isolation": "temporary_directory",
            "pdf_path": str(pdf_path.resolve()),
            "ground_truth_path": str(ground_truth_path.resolve()),
            "pdf_sha256": file_hash,
            "chunks_saved": chunks_saved,
            "citation_hit_definition": (
                "expected_page in final cited_pages"
            ),
            "retrieval_evidence_definition": (
                "all Ground Truth evidence segments occur in one chunk sent "
                "to generation"
            ),
        },
        "summary": calculate_citation_metrics(results),
        "failures": failures,
        "retrieval_evidence_citation_mismatches": [
            failure
            for failure in failures
            if failure["failure_reason"] == "llm_cited_other_source"
        ],
        "results": results,
    }


def print_citation_report(report: dict) -> None:
    for result in report["results"]:
        status = "HIT" if result["citation_hit"] else "MISS"
        print(
            f"{result['question_id']} | Citation {status} | "
            f"expected={result['expected_page']} | "
            f"cited={result['cited_pages']}"
        )
        print(f"Question: {result['question']}")
        print(f"Retrieved pages: {result['retrieved_pages']}")
        print(f"Retrieval evidence: {result['retrieval_evidence_hit']}")
        print(f"Failure reason: {result['failure_reason']}")
        print(f"Answer: {result['answer']}")
        print()

    summary = report["summary"]
    print("RAG CITATION END-TO-END")
    print("=======================")
    print(f"Questions: {summary['questions']}")
    print(
        f"Citation Hit: {summary['citation_hits']}/"
        f"{summary['questions']} "
        f"({summary['citation_hit_percentage']:.2f}%)"
    )
    print(f"Failed questions: {summary['failed_questions']}")
    print(
        "Retrieval evidence but wrong citation: "
        f"{summary['retrieval_evidence_but_wrong_citation']}"
    )
    print(
        "Retrieval evidence but no citation: "
        f"{summary['retrieval_evidence_but_no_citation']}"
    )
    print(f"Generation errors: {summary['generation_errors']}")

    if report["failures"]:
        print("\nFAILURES")
        print("========")
        for failure in report["failures"]:
            print(
                f"{failure['question_id']} | expected="
                f"{failure['expected_page']} | cited={failure['cited_pages']} | "
                f"reason={failure['failure_reason']}"
            )


def run_citation_evaluation(
    pdf_path: Path = DEFAULT_PDF_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    results_path: Path = DEFAULT_RESULTS_PATH,
) -> dict:
    questions = parse_ground_truth(ground_truth_path)
    if len(questions) != 25:
        raise ValueError(
            f"El benchmark debe contener 25 preguntas; contiene {len(questions)}."
        )

    with tempfile.TemporaryDirectory(prefix="rag-citations-") as database_path:
        configure_vector_db(database_path)
        try:
            document_id, chunks_saved, file_hash = ingest_benchmark_pdf(pdf_path)
            results = evaluate_citation_questions(questions, document_id)
        finally:
            close_isolated_vector_db()

    report = build_citation_report(
        results,
        pdf_path=pdf_path,
        ground_truth_path=ground_truth_path,
        file_hash=file_hash,
        chunks_saved=chunks_saved,
    )
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print_citation_report(report)
    print(f"\nJSON: {results_path.resolve()}")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate final RAG citation pages against the 25-question "
            "Ground Truth."
        )
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument(
        "--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH_PATH
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_citation_evaluation(args.pdf, args.ground_truth, args.output)


if __name__ == "__main__":
    main()
