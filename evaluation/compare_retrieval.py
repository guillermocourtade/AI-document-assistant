from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from evaluation.evaluate_retrieval import (
    DEFAULT_GROUND_TRUTH_PATH,
    DEFAULT_PDF_PATH,
    EVALUATION_DIR,
    MAX_DISTANCE,
    BenchmarkQuestion,
    build_question_result,
    calculate_group_metrics,
    calculate_metrics,
    close_isolated_vector_db,
    evaluate_questions,
    ingest_benchmark_pdf,
    load_chunk_index_lookup,
    parse_ground_truth,
    rank_retrieved_chunks,
)
from app.services.vector_db_service import (
    configure_vector_db,
    search_similar_chunks_with_metadata,
)


BASELINE_SIZE = 4
TOP6_SIZE = 6
RERANK_CANDIDATE_POOL_SIZE = 10
RERANK_FINAL_SIZE = 4
RERANKER_LIBRARY = "FlashRank==0.2.10"
RERANKER_MODEL = "ms-marco-MultiBERT-L-12"

RESULTS_DIR = EVALUATION_DIR / "results"
DAY24_BASELINE_RESULTS_PATH = RESULTS_DIR / "day24_baseline_results.json"
TOP6_RESULTS_PATH = RESULTS_DIR / "top6_results.json"
RERANK_RESULTS_PATH = RESULTS_DIR / "rerank_results.json"
COMPARISON_RESULTS_PATH = RESULTS_DIR / "comparison_results.json"

RerankFunction = Callable[[str, list[dict]], list[dict]]


def average_context_chars(results: Iterable[dict], k: int) -> float:
    result_list = list(results)
    if not result_list:
        return 0.0
    return sum(
        sum(len(chunk["text"]) for chunk in result["retrieved_results"][:k])
        for result in result_list
    ) / len(result_list)


def calculate_context_growth(baseline_size: int, experiment_size: int) -> dict:
    ratio = experiment_size / baseline_size
    return {
        "baseline_chunks": baseline_size,
        "experiment_chunks": experiment_size,
        "ratio": ratio,
        "increase_percentage": (ratio - 1.0) * 100.0,
    }


def rerank_candidates(
    question: str,
    candidates: list[dict],
    rerank_function: RerankFunction,
    final_size: int = RERANK_FINAL_SIZE,
) -> tuple[list[dict], list[dict]]:
    passages = [
        {
            "id": candidate["rank"],
            "text": candidate["text"],
            "meta": candidate.copy(),
        }
        for candidate in candidates
    ]
    reranked_passages = rerank_function(question, passages)
    reranked_results: list[dict] = []

    for reranked_rank, passage in enumerate(reranked_passages, start=1):
        result = passage["meta"].copy()
        result["vector_rank"] = result.pop("rank")
        result["rank"] = reranked_rank
        result["reranker_score"] = float(passage["score"])
        reranked_results.append(result)

    return reranked_results[:final_size], reranked_results


def evaluate_reranked_questions(
    questions: Iterable[BenchmarkQuestion],
    document_id: str,
    chunk_index_lookup: dict[tuple, int],
    rerank_function: RerankFunction,
    retrieval_function=search_similar_chunks_with_metadata,
    candidate_pool_size: int = RERANK_CANDIDATE_POOL_SIZE,
    final_size: int = RERANK_FINAL_SIZE,
) -> tuple[list[dict], dict]:
    results: list[dict] = []
    retrieval_seconds = 0.0
    reranking_seconds = 0.0

    for question in questions:
        retrieval_started = perf_counter()
        retrieved = retrieval_function(
            question=question.question,
            n_results=candidate_pool_size,
            document_id=document_id,
            max_distance=MAX_DISTANCE,
        )
        retrieval_seconds += perf_counter() - retrieval_started
        candidates = rank_retrieved_chunks(retrieved, chunk_index_lookup)

        reranking_started = perf_counter()
        final_results, reranked_candidates = rerank_candidates(
            question.question,
            candidates,
            rerank_function,
            final_size,
        )
        reranking_seconds += perf_counter() - reranking_started

        result = build_question_result(
            question,
            final_results,
            page_ks=range(1, final_size + 1),
            evidence_ks=(final_size,),
        )
        result["candidate_results"] = candidates
        result["reranked_candidates"] = reranked_candidates
        result["candidate_pool_returned"] = len(candidates)
        result["final_context_returned"] = len(final_results)
        results.append(result)

    return results, {
        "retrieval_seconds": retrieval_seconds,
        "reranking_seconds": reranking_seconds,
        "total_seconds": retrieval_seconds + reranking_seconds,
    }


def build_experiment_report(
    name: str,
    results: list[dict],
    configuration: dict,
    timing: dict,
) -> dict:
    questions = len(results)
    timing = {
        **timing,
        "average_seconds_per_question": (
            timing["total_seconds"] / questions if questions else 0.0
        ),
    }
    return {
        "experiment": name,
        "configuration": configuration,
        "summary": calculate_metrics(results),
        "category_metrics": calculate_group_metrics(results, "category"),
        "difficulty_metrics": calculate_group_metrics(results, "difficulty"),
        "context": {
            "average_final_context_chars": average_context_chars(
                results, configuration["final_context_size"]
            ),
        },
        "timing": timing,
        "results": results,
    }


def _evaluate_vector_configuration(
    questions: list[BenchmarkQuestion],
    document_id: str,
    chunk_index_lookup: dict[tuple, int],
    n_results: int,
    evidence_ks: tuple[int, ...],
) -> tuple[list[dict], dict]:
    started = perf_counter()
    results = evaluate_questions(
        questions,
        document_id,
        chunk_index_lookup=chunk_index_lookup,
        n_results=n_results,
        max_distance=MAX_DISTANCE,
        evidence_ks=evidence_ks,
    )
    total_seconds = perf_counter() - started
    return results, {
        "retrieval_seconds": total_seconds,
        "reranking_seconds": 0.0,
        "total_seconds": total_seconds,
    }


def _create_flashrank(cache_dir: Path):
    from flashrank import Ranker, RerankRequest

    started = perf_counter()
    ranker = Ranker(
        model_name=RERANKER_MODEL,
        cache_dir=str(cache_dir),
        max_length=512,
        log_level="WARNING",
    )
    initialization_seconds = perf_counter() - started

    def rerank(question: str, passages: list[dict]) -> list[dict]:
        return ranker.rerank(RerankRequest(query=question, passages=passages))

    return rerank, initialization_seconds


def _q01_diagnostic(
    baseline_results: list[dict],
    top6_results: list[dict],
    rerank_results: list[dict],
) -> dict:
    baseline = next(r for r in baseline_results if r["question_id"] == "Q01")
    top6 = next(r for r in top6_results if r["question_id"] == "Q01")
    reranked = next(r for r in rerank_results if r["question_id"] == "Q01")
    top6_chunk = next(
        item for item in top6["retrieved_results"] if item["chunk_index"] == 79
    )
    reranked_chunk = next(
        item for item in reranked["reranked_candidates"] if item["chunk_index"] == 79
    )
    return {
        "baseline": {
            "vector_rank_of_chunk_79": 6,
            "final_selected": any(
                item["chunk_index"] == 79 for item in baseline["retrieved_results"]
            ),
            "evidence_hit_at_4": baseline["evidence_hit_at_4"],
        },
        "top6": {
            "vector_rank": top6_chunk["rank"],
            "final_selected": True,
            "evidence_hit_at_4": top6["evidence_hit_at_4"],
            "evidence_hit_at_6": top6["evidence_hit_at_6"],
        },
        "rerank": {
            "vector_rank": reranked_chunk["vector_rank"],
            "reranked_rank": reranked_chunk["rank"],
            "reranker_score": reranked_chunk["reranker_score"],
            "final_selected": reranked_chunk["rank"] <= RERANK_FINAL_SIZE,
            "evidence_hit_at_4": reranked["evidence_hit_at_4"],
        },
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_comparison(
    pdf_path: Path = DEFAULT_PDF_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    reranker_cache: Path | None = None,
) -> dict:
    questions = parse_ground_truth(ground_truth_path)
    if len(questions) != 25:
        raise ValueError("El benchmark debe contener exactamente 25 preguntas.")

    reranker_cache = reranker_cache or (
        Path(tempfile.gettempdir()) / "rag-evaluation-flashrank-cache"
    )
    with tempfile.TemporaryDirectory(prefix="rag-day24-") as database_path:
        configure_vector_db(database_path)
        try:
            ingestion_started = perf_counter()
            document_id, chunks_saved, file_hash = ingest_benchmark_pdf(pdf_path)
            ingestion_seconds = perf_counter() - ingestion_started
            chunk_index_lookup = load_chunk_index_lookup(document_id)

            baseline_results, baseline_timing = _evaluate_vector_configuration(
                questions,
                document_id,
                chunk_index_lookup,
                BASELINE_SIZE,
                (4,),
            )
            top6_results, top6_timing = _evaluate_vector_configuration(
                questions,
                document_id,
                chunk_index_lookup,
                TOP6_SIZE,
                (4, 6),
            )

            rerank_function, reranker_initialization_seconds = _create_flashrank(
                reranker_cache
            )
            rerank_results, rerank_timing = evaluate_reranked_questions(
                questions,
                document_id,
                chunk_index_lookup,
                rerank_function,
            )
        finally:
            close_isolated_vector_db()

    common_configuration = {
        "max_distance": MAX_DISTANCE,
        "pdf_sha256": file_hash,
        "chunks_saved": chunks_saved,
        "shared_ingestion_seconds": ingestion_seconds,
        "vector_database_isolation": "temporary_directory",
    }
    baseline_report = build_experiment_report(
        "baseline_vector_top4",
        baseline_results,
        {
            **common_configuration,
            "candidate_pool_size": BASELINE_SIZE,
            "final_context_size": BASELINE_SIZE,
            "reranker": None,
        },
        baseline_timing,
    )
    top6_report = build_experiment_report(
        "vector_top6",
        top6_results,
        {
            **common_configuration,
            "candidate_pool_size": TOP6_SIZE,
            "final_context_size": TOP6_SIZE,
            "reranker": None,
        },
        top6_timing,
    )
    top6_report["context"].update(
        {
            "average_context_chars_first_4": average_context_chars(
                top6_results, 4
            ),
            "growth_vs_top4": calculate_context_growth(4, 6),
        }
    )
    rerank_timing["reranker_initialization_seconds"] = (
        reranker_initialization_seconds
    )
    rerank_report = build_experiment_report(
        "vector_top10_flashrank_top4",
        rerank_results,
        {
            **common_configuration,
            "candidate_pool_size": RERANK_CANDIDATE_POOL_SIZE,
            "final_context_size": RERANK_FINAL_SIZE,
            "reranker_library": RERANKER_LIBRARY,
            "reranker_model": RERANKER_MODEL,
            "reranker_max_length": 512,
        },
        rerank_timing,
    )

    comparison = {
        "configuration": {
            **common_configuration,
            "reranker_library": RERANKER_LIBRARY,
            "reranker_model": RERANKER_MODEL,
        },
        "context_growth_top6_vs_top4": calculate_context_growth(4, 6),
        "experiments": {
            "baseline_top4": {
                "summary": baseline_report["summary"],
                "context": baseline_report["context"],
                "timing": baseline_report["timing"],
                "candidate_pool_size": 4,
                "final_context_size": 4,
            },
            "top6": {
                "summary": top6_report["summary"],
                "context": top6_report["context"],
                "timing": top6_report["timing"],
                "candidate_pool_size": 6,
                "final_context_size": 6,
            },
            "top10_rerank_top4": {
                "summary": rerank_report["summary"],
                "context": rerank_report["context"],
                "timing": rerank_report["timing"],
                "candidate_pool_size": 10,
                "final_context_size": 4,
            },
        },
        "q01": _q01_diagnostic(
            baseline_results, top6_results, rerank_results
        ),
    }

    _write_json(DAY24_BASELINE_RESULTS_PATH, baseline_report)
    _write_json(TOP6_RESULTS_PATH, top6_report)
    _write_json(RERANK_RESULTS_PATH, rerank_report)
    _write_json(COMPARISON_RESULTS_PATH, comparison)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return comparison


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare vector Top-4, Top-6, and Top-10 reranked to Top-4."
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument(
        "--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH_PATH
    )
    parser.add_argument("--reranker-cache", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_comparison(args.pdf, args.ground_truth, args.reranker_cache)


if __name__ == "__main__":
    main()
