from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from fastapi.testclient import TestClient

from app.logger import logger
from app.main import app
from app.services.openai_service import CITED_RESPONSE_MODEL
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
    ingest_benchmark_pdf,
    parse_ground_truth,
)


EVALUATION_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_PATH = EVALUATION_DIR / "results" / "latency_benchmark.json"
METRIC_NAMES = (
    "total_latency_ms",
    "retrieval_latency_ms",
    "openai_generation_latency_ms",
    "input_tokens",
    "output_tokens",
)
PERCENTILE_METHOD = "nearest_rank"
OUTLIER_METHOD = "total_latency_ms > Q3 + 1.5 * IQR"


class RagLogCapture(logging.Handler):
    """Captura eventos RAG ya medidos por la observabilidad productiva."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.observations: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() != "rag_request_completed":
            return

        fields = getattr(record, "structured_data", None)
        if isinstance(fields, dict):
            self.observations.append(dict(fields))


@contextmanager
def capture_rag_logs() -> Iterator[RagLogCapture]:
    """Evita ruido en consola y conserva solamente la telemetria RAG."""

    capture = RagLogCapture()
    previous_handlers = list(logger.handlers)
    logger.handlers = [capture]

    try:
        yield capture
    finally:
        logger.handlers = previous_handlers


def percentile_nearest_rank(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("No se puede calcular un percentil sin valores.")
    if not 0 < percentile <= 1:
        raise ValueError("El percentil debe estar en el intervalo (0, 1].")

    rank = math.ceil(percentile * len(ordered))
    return ordered[rank - 1]


def calculate_distribution(
    values: Iterable[int | float | None],
) -> dict:
    all_values = list(values)
    available = [
        float(value)
        for value in all_values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    missing_samples = len(all_values) - len(available)

    if not available:
        return {
            "samples": 0,
            "missing_samples": missing_samples,
            "average": None,
            "median_p50": None,
            "p95": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "samples": len(available),
        "missing_samples": missing_samples,
        "average": round(statistics.fmean(available), 3),
        "median_p50": round(statistics.median(available), 3),
        "p95": round(percentile_nearest_rank(available, 0.95), 3),
        "minimum": round(min(available), 3),
        "maximum": round(max(available), 3),
    }


def calculate_metric_statistics(results: Iterable[dict]) -> dict:
    result_list = list(results)
    return {
        metric_name: calculate_distribution(
            result.get(metric_name) for result in result_list
        )
        for metric_name in METRIC_NAMES
    }


def calculate_latency_shares(results: Iterable[dict]) -> dict:
    complete_results = [
        result
        for result in results
        if all(
            isinstance(result.get(metric), (int, float))
            and not isinstance(result.get(metric), bool)
            for metric in (
                "total_latency_ms",
                "retrieval_latency_ms",
                "openai_generation_latency_ms",
            )
        )
    ]
    total_latency = sum(
        result["total_latency_ms"] for result in complete_results
    )
    retrieval_latency = sum(
        result["retrieval_latency_ms"] for result in complete_results
    )
    generation_latency = sum(
        result["openai_generation_latency_ms"]
        for result in complete_results
    )

    if total_latency <= 0:
        return {
            "samples": len(complete_results),
            "retrieval_percentage": None,
            "openai_generation_percentage": None,
            "other_percentage": None,
        }

    retrieval_percentage = retrieval_latency / total_latency * 100
    generation_percentage = generation_latency / total_latency * 100

    return {
        "samples": len(complete_results),
        "retrieval_percentage": round(retrieval_percentage, 3),
        "openai_generation_percentage": round(generation_percentage, 3),
        "other_percentage": round(
            max(0.0, 100.0 - retrieval_percentage - generation_percentage),
            3,
        ),
    }


def detect_total_latency_outliers(results: Iterable[dict]) -> dict:
    measured_results = [
        result
        for result in results
        if isinstance(result.get("total_latency_ms"), (int, float))
        and not isinstance(result.get("total_latency_ms"), bool)
    ]
    latencies = [result["total_latency_ms"] for result in measured_results]

    if len(latencies) < 4:
        return {
            "method": OUTLIER_METHOD,
            "threshold_ms": None,
            "outliers": [],
            "note": "Se requieren al menos 4 muestras para aplicar IQR.",
        }

    q1, _, q3 = statistics.quantiles(
        latencies,
        n=4,
        method="inclusive",
    )
    threshold = q3 + 1.5 * (q3 - q1)
    outliers = [
        {
            "question_id": result["question_id"],
            "repetition": result["repetition"],
            "request_id": result["request_id"],
            "total_latency_ms": result["total_latency_ms"],
        }
        for result in measured_results
        if result["total_latency_ms"] > threshold
    ]

    return {
        "method": OUTLIER_METHOD,
        "threshold_ms": round(threshold, 3),
        "outliers": sorted(
            outliers,
            key=lambda item: item["total_latency_ms"],
            reverse=True,
        ),
        "note": None,
    }


def slowest_at_p95(results: Iterable[dict]) -> list[dict]:
    measured_results = [
        result
        for result in results
        if isinstance(result.get("total_latency_ms"), (int, float))
        and not isinstance(result.get("total_latency_ms"), bool)
    ]
    if not measured_results:
        return []

    p95 = percentile_nearest_rank(
        (result["total_latency_ms"] for result in measured_results),
        0.95,
    )
    return [
        {
            "question_id": result["question_id"],
            "repetition": result["repetition"],
            "request_id": result["request_id"],
            "total_latency_ms": result["total_latency_ms"],
        }
        for result in sorted(
            measured_results,
            key=lambda item: item["total_latency_ms"],
            reverse=True,
        )
        if result["total_latency_ms"] >= p95
    ]


def select_questions(
    questions: list[BenchmarkQuestion],
    question_ids: Iterable[str] | None,
) -> list[BenchmarkQuestion]:
    if question_ids is None:
        return questions

    requested_ids = list(dict.fromkeys(question_ids))
    questions_by_id = {question.question_id: question for question in questions}
    unknown_ids = [
        question_id
        for question_id in requested_ids
        if question_id not in questions_by_id
    ]
    if unknown_ids:
        raise ValueError(
            "IDs de pregunta desconocidos: " + ", ".join(unknown_ids)
        )

    return [questions_by_id[question_id] for question_id in requested_ids]


def _safe_request_result(
    *,
    question_id: str,
    repetition: int,
    http_status: int,
    observation: dict,
) -> dict:
    return {
        "question_id": question_id,
        "repetition": repetition,
        "request_id": observation.get("request_id"),
        "endpoint": observation.get("endpoint"),
        "status": observation.get("status"),
        "http_status": http_status,
        "total_latency_ms": observation.get("total_latency_ms"),
        "retrieval_latency_ms": observation.get("retrieval_latency_ms"),
        "openai_generation_latency_ms": observation.get(
            "openai_generation_latency_ms"
        ),
        "input_tokens": observation.get("input_tokens"),
        "output_tokens": observation.get("output_tokens"),
        "model": observation.get("model"),
        "chunks_retrieved": observation.get("chunks_retrieved"),
        "error_type": observation.get("error_type"),
    }


def execute_requests(
    questions: Iterable[BenchmarkQuestion],
    document_id: str,
    *,
    repetitions: int = 1,
) -> list[dict]:
    if repetitions < 1:
        raise ValueError("repetitions debe ser mayor o igual que 1.")

    question_list = list(questions)
    results: list[dict] = []

    with capture_rag_logs() as capture:
        with TestClient(app, raise_server_exceptions=False) as client:
            for repetition in range(1, repetitions + 1):
                for question in question_list:
                    print(
                        f"{question.question_id} | repeticion "
                        f"{repetition}/{repetitions}"
                    )
                    observations_before = len(capture.observations)
                    response = client.post(
                        "/chat/document",
                        json={
                            "message": question.question,
                            "document_id": document_id,
                        },
                    )
                    new_observations = capture.observations[
                        observations_before:
                    ]
                    if len(new_observations) != 1:
                        raise RuntimeError(
                            "Se esperaba exactamente un evento RAG por request; "
                            f"se capturaron {len(new_observations)}."
                        )

                    results.append(
                        _safe_request_result(
                            question_id=question.question_id,
                            repetition=repetition,
                            http_status=response.status_code,
                            observation=new_observations[0],
                        )
                    )

    return results


def build_report(
    results: list[dict],
    questions: list[BenchmarkQuestion],
    *,
    pdf_path: Path,
    ground_truth_path: Path,
    file_hash: str,
    chunks_saved: int,
    repetitions: int,
) -> dict:
    sample_size = len(results)
    p95_rank = math.ceil(0.95 * sample_size) if sample_size else None
    return {
        "benchmark": "rag_end_to_end_latency",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "endpoint": "/chat/document",
            "questions": len(questions),
            "question_ids": [question.question_id for question in questions],
            "category_distribution": dict(
                Counter(question.category for question in questions)
            ),
            "difficulty_distribution": dict(
                Counter(question.difficulty for question in questions)
            ),
            "repetitions": repetitions,
            "requests": sample_size,
            "model": CITED_RESPONSE_MODEL,
            "n_results": N_RESULTS,
            "max_distance": MAX_DISTANCE,
            "chunk_size": CHUNK_SIZE,
            "overlap": OVERLAP,
            "vector_database_isolation": "temporary_directory",
            "pdf_path": str(pdf_path.resolve()),
            "ground_truth_path": str(ground_truth_path.resolve()),
            "pdf_sha256": file_hash,
            "chunks_saved": chunks_saved,
            "measurement_source": "rag_request_completed structured log",
            "percentile_method": PERCENTILE_METHOD,
            "outlier_method": OUTLIER_METHOD,
        },
        "summary": {
            "successful_requests": sum(
                result["http_status"] == 200 and result["status"] == "success"
                for result in results
            ),
            "failed_requests": sum(
                result["http_status"] != 200 or result["status"] != "success"
                for result in results
            ),
            "metrics": calculate_metric_statistics(results),
            "latency_share": calculate_latency_shares(results),
            "outlier_analysis": detect_total_latency_outliers(results),
            "requests_at_or_above_p95": slowest_at_p95(results),
            "p95_caution": {
                "sample_size": sample_size,
                "nearest_rank": p95_rank,
                "interpret_with_caution": sample_size < 100,
                "note": (
                    "Con una muestra pequena, p95 depende de muy pocas "
                    "observaciones extremas y debe considerarse orientativo."
                    if sample_size < 100
                    else None
                ),
            },
        },
        "requests": results,
    }


def print_report(report: dict) -> None:
    summary = report["summary"]
    print("\nRAG LATENCY BENCHMARK")
    print("=====================")
    print(f"Requests: {report['configuration']['requests']}")
    print(f"Successful: {summary['successful_requests']}")
    print(f"Failed: {summary['failed_requests']}")

    print("\nMetricas")
    print("--------")
    for metric_name, metrics in summary["metrics"].items():
        print(
            f"{metric_name}: avg={metrics['average']} | "
            f"p50={metrics['median_p50']} | p95={metrics['p95']} | "
            f"min={metrics['minimum']} | max={metrics['maximum']} | "
            f"n={metrics['samples']}"
        )

    shares = summary["latency_share"]
    print("\nDistribucion del tiempo total")
    print("-----------------------------")
    print(f"Retrieval: {shares['retrieval_percentage']}%")
    print(f"OpenAI generation: {shares['openai_generation_percentage']}%")
    print(f"Other: {shares['other_percentage']}%")

    analysis = summary["outlier_analysis"]
    print("\nOutliers")
    print("--------")
    print(f"IQR threshold: {analysis['threshold_ms']} ms")
    if analysis["outliers"]:
        for outlier in analysis["outliers"]:
            print(
                f"{outlier['question_id']} rep={outlier['repetition']} | "
                f"{outlier['total_latency_ms']} ms"
            )
    else:
        print("No IQR outliers detected.")

    slow_requests = summary["requests_at_or_above_p95"]
    print("\nRequests at or above p95")
    print("------------------------")
    if slow_requests:
        for request in slow_requests:
            print(
                f"{request['question_id']} rep={request['repetition']} | "
                f"{request['total_latency_ms']} ms"
            )
    else:
        print("No measured requests.")

    caution = summary["p95_caution"]
    if caution["interpret_with_caution"]:
        print(
            "\nCAUTION: p95 is nearest-rank "
            f"{caution['nearest_rank']} of {caution['sample_size']}; "
            "it is sensitive to very few slow requests."
        )


def run_benchmark(
    pdf_path: Path = DEFAULT_PDF_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    results_path: Path = DEFAULT_RESULTS_PATH,
    *,
    question_ids: Iterable[str] | None = None,
    repetitions: int = 1,
) -> dict:
    all_questions = parse_ground_truth(ground_truth_path)
    questions = select_questions(all_questions, question_ids)

    with tempfile.TemporaryDirectory(prefix="rag-latency-") as database_path:
        configure_vector_db(database_path)
        try:
            document_id, chunks_saved, file_hash = ingest_benchmark_pdf(pdf_path)
            results = execute_requests(
                questions,
                document_id,
                repetitions=repetitions,
            )
        finally:
            close_isolated_vector_db()

    report = build_report(
        results,
        questions,
        pdf_path=pdf_path,
        ground_truth_path=ground_truth_path,
        file_hash=file_hash,
        chunks_saved=chunks_saved,
        repetitions=repetitions,
    )
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print_report(report)
    print(f"\nJSON: {results_path.resolve()}")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark end-to-end RAG latency using existing telemetry."
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=DEFAULT_GROUND_TRUTH_PATH,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument(
        "--question-ids",
        help="Comma-separated IDs; defaults to all Ground Truth questions.",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    question_ids = (
        [item.strip() for item in args.question_ids.split(",") if item.strip()]
        if args.question_ids
        else None
    )
    run_benchmark(
        args.pdf,
        args.ground_truth,
        args.output,
        question_ids=question_ids,
        repetitions=args.repetitions,
    )


if __name__ == "__main__":
    main()
