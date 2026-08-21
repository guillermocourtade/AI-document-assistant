from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable

from app.services.openai_service import generate_response
from evaluation.compare_retrieval import (
    DAY24_BASELINE_RESULTS_PATH,
    RESULTS_DIR,
    TOP6_RESULTS_PATH,
)


GENERATION_RESULTS_PATH = RESULTS_DIR / "generation_top4_vs_top6.json"
GENERATION_MODEL = "gpt-4.1-mini"
EXPECTED_QUESTION_COUNT = 25
TOP4_SIZE = 4
TOP6_SIZE = 6

GenerationFunction = Callable[[str, list[str]], str]


def normalize_answer(answer: str) -> str:
    """Normalize only whitespace, preserving wording, case, and punctuation."""
    return re.sub(r"\s+", " ", answer).strip()


def classify_answer_change(top4_answer: str, top6_answer: str) -> str:
    return (
        "UNCHANGED"
        if normalize_answer(top4_answer) == normalize_answer(top6_answer)
        else "CHANGED"
    )


def calculate_context_chars(retrieved_results: Iterable[dict]) -> int:
    return sum(len(result["text"]) for result in retrieved_results)


def calculate_generation_statistics(results: Iterable[dict]) -> dict:
    result_list = list(results)
    comparable = [
        result for result in result_list if result["comparison_status"] != "ERROR"
    ]
    changed_questions = [
        result["question_id"]
        for result in comparable
        if result["comparison_status"] == "CHANGED"
    ]
    unchanged_questions = [
        result["question_id"]
        for result in comparable
        if result["comparison_status"] == "UNCHANGED"
    ]
    top4_context_chars = [result["top4"]["context_chars"] for result in result_list]
    top6_context_chars = [result["top6"]["context_chars"] for result in result_list]
    top4_seconds = [result["top4"]["generation_seconds"] for result in result_list]
    top6_seconds = [result["top6"]["generation_seconds"] for result in result_list]
    top4_total_seconds = sum(top4_seconds)
    top6_total_seconds = sum(top6_seconds)
    top4_average_context = (
        sum(top4_context_chars) / len(top4_context_chars)
        if top4_context_chars
        else 0.0
    )
    top6_average_context = (
        sum(top6_context_chars) / len(top6_context_chars)
        if top6_context_chars
        else 0.0
    )
    context_growth = (
        ((top6_average_context / top4_average_context) - 1.0) * 100.0
        if top4_average_context
        else 0.0
    )

    return {
        "questions": len(result_list),
        "generations_attempted": len(result_list) * 2,
        "generations_succeeded": sum(
            result[configuration]["error"] is None
            for result in result_list
            for configuration in ("top4", "top6")
        ),
        "generation_errors": sum(
            result[configuration]["error"] is not None
            for result in result_list
            for configuration in ("top4", "top6")
        ),
        "comparable_questions": len(comparable),
        "identical_answers": len(unchanged_questions),
        "different_answers": len(changed_questions),
        "unchanged_questions": unchanged_questions,
        "changed_questions": changed_questions,
        "uncomparable_questions": [
            result["question_id"]
            for result in result_list
            if result["comparison_status"] == "ERROR"
        ],
        "context": {
            "top4_average_chars": top4_average_context,
            "top6_average_chars": top6_average_context,
            "growth_percentage": context_growth,
        },
        "generation_timing": {
            "top4_total_seconds": top4_total_seconds,
            "top4_average_seconds": (
                top4_total_seconds / len(top4_seconds) if top4_seconds else 0.0
            ),
            "top6_total_seconds": top6_total_seconds,
            "top6_average_seconds": (
                top6_total_seconds / len(top6_seconds) if top6_seconds else 0.0
            ),
            "combined_total_seconds": top4_total_seconds + top6_total_seconds,
        },
    }


def serialize_generation_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pair_retrieval_results(
    top4_report: dict,
    top6_report: dict,
    *,
    expected_question_count: int | None = EXPECTED_QUESTION_COUNT,
) -> list[tuple[dict, dict]]:
    top4_results = top4_report["results"]
    top6_by_id = {result["question_id"]: result for result in top6_report["results"]}

    if expected_question_count is not None and len(top4_results) != expected_question_count:
        raise ValueError(
            f"Expected {expected_question_count} Top-4 questions, got {len(top4_results)}"
        )
    if len(top6_by_id) != len(top4_results):
        raise ValueError("Top-4 and Top-6 reports do not contain the same questions")

    pairs: list[tuple[dict, dict]] = []
    for top4_result in top4_results:
        question_id = top4_result["question_id"]
        if question_id not in top6_by_id:
            raise ValueError(f"Missing {question_id} in Top-6 report")
        top6_result = top6_by_id[question_id]
        if top4_result["question"] != top6_result["question"]:
            raise ValueError(f"Question text differs for {question_id}")
        if top4_result["expected_answer"] != top6_result["expected_answer"]:
            raise ValueError(f"Expected answer differs for {question_id}")
        if len(top4_result["retrieved_results"]) != TOP4_SIZE:
            raise ValueError(f"{question_id} does not contain exactly four Top-4 chunks")
        if len(top6_result["retrieved_results"]) != TOP6_SIZE:
            raise ValueError(f"{question_id} does not contain exactly six Top-6 chunks")
        if (
            top4_result["retrieved_results"]
            != top6_result["retrieved_results"][:TOP4_SIZE]
        ):
            raise ValueError(f"Top-4 is not the prefix of Top-6 for {question_id}")
        pairs.append((top4_result, top6_result))

    return pairs


def _retrieval_metrics(result: dict) -> dict:
    return {
        key: value
        for key, value in result.items()
        if key.startswith("page_hit_at_")
        or key.startswith("evidence_hit_at_")
        or key in ("first_expected_page_rank", "reciprocal_rank")
    }


def _generate_configuration(
    question: str,
    retrieval_result: dict,
    generation_function: GenerationFunction,
) -> dict:
    retrieved_results = retrieval_result["retrieved_results"]
    chunks = [result["text"] for result in retrieved_results]
    started = perf_counter()
    answer: str | None = None
    error: dict | None = None
    try:
        answer = generation_function(question, chunks)
    except Exception as exc:  # Keep the 50-call experiment auditable after a failure.
        error = {"type": type(exc).__name__, "message": str(exc)}
    generation_seconds = perf_counter() - started

    return {
        "retrieved_pages": retrieval_result["retrieved_pages"],
        "retrieved_chunk_indices": [
            result["chunk_index"] for result in retrieved_results
        ],
        "retrieved_results": retrieved_results,
        "retrieval_metrics": _retrieval_metrics(retrieval_result),
        "context_chars": calculate_context_chars(retrieved_results),
        "answer": answer,
        "generation_seconds": generation_seconds,
        "error": error,
    }


def run_generation_comparison(
    pairs: Iterable[tuple[dict, dict]],
    generation_function: GenerationFunction = generate_response,
    progress_function: Callable[[str], None] | None = print,
) -> list[dict]:
    results: list[dict] = []
    for top4_retrieval, top6_retrieval in pairs:
        question_id = top4_retrieval["question_id"]
        question = top4_retrieval["question"]

        if progress_function:
            progress_function(f"{question_id}: generating Top-4")
        top4 = _generate_configuration(
            question, top4_retrieval, generation_function
        )

        if progress_function:
            progress_function(f"{question_id}: generating Top-6")
        top6 = _generate_configuration(
            question, top6_retrieval, generation_function
        )

        comparison_status = (
            "ERROR"
            if top4["answer"] is None or top6["answer"] is None
            else classify_answer_change(top4["answer"], top6["answer"])
        )
        results.append(
            {
                key: top4_retrieval[key]
                for key in (
                    "question_id",
                    "question",
                    "expected_answer",
                    "section",
                    "expected_page",
                    "evidence",
                    "difficulty",
                    "category",
                )
            }
            | {
                "top4": top4,
                "top6": top6,
                "comparison_status": comparison_status,
                "answer_changed": (
                    comparison_status == "CHANGED"
                    if comparison_status != "ERROR"
                    else None
                ),
            }
        )

    return results


def build_generation_report(results: list[dict]) -> dict:
    return {
        "experiment": "generation_top4_vs_top6",
        "configuration": {
            "generation_function": "app.services.openai_service.generate_response",
            "generation_model": GENERATION_MODEL,
            "temperature": "not explicitly set by production generate_response()",
            "execution_order": "for each question: Top-4, then Top-6",
            "answer_comparison": "exact after whitespace normalization only",
            "top4_retrieval_source": str(DAY24_BASELINE_RESULTS_PATH),
            "top6_retrieval_source": str(TOP6_RESULTS_PATH),
            "retrieval_reexecuted": False,
            "retrieval_isolation_reason": (
                "Reuse frozen Day 24 retrieval outputs to isolate generation and "
                "avoid embedding or vector-database drift"
            ),
        },
        "summary": calculate_generation_statistics(results),
        "results": results,
    }


def main() -> None:
    top4_report = _load_report(DAY24_BASELINE_RESULTS_PATH)
    top6_report = _load_report(TOP6_RESULTS_PATH)
    pairs = pair_retrieval_results(top4_report, top6_report)
    results = run_generation_comparison(pairs)
    report = build_generation_report(results)
    serialize_generation_report(report, GENERATION_RESULTS_PATH)

    summary = report["summary"]
    print(f"Wrote {GENERATION_RESULTS_PATH}")
    print(f"Generations attempted: {summary['generations_attempted']}")
    print(f"Generation errors: {summary['generation_errors']}")
    print(f"Identical answers: {summary['identical_answers']}")
    print(f"Different answers: {summary['different_answers']}")
    print(f"Changed questions: {summary['changed_questions']}")


if __name__ == "__main__":
    main()
