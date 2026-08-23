import pytest

from evaluation.benchmark_latency import (
    _safe_request_result,
    calculate_distribution,
    calculate_latency_shares,
    calculate_metric_statistics,
    detect_total_latency_outliers,
    percentile_nearest_rank,
    slowest_at_p95,
)


def _result(
    question_id: str,
    total: float,
    retrieval: float,
    generation: float,
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
) -> dict:
    return {
        "question_id": question_id,
        "repetition": 1,
        "request_id": f"request-{question_id}",
        "total_latency_ms": total,
        "retrieval_latency_ms": retrieval,
        "openai_generation_latency_ms": generation,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def test_nearest_rank_percentile_is_deterministic():
    values = list(range(1, 21))

    assert percentile_nearest_rank(values, 0.50) == 10
    assert percentile_nearest_rank(values, 0.95) == 19


def test_distribution_calculates_summary_and_missing_samples():
    distribution = calculate_distribution([10, 20, 30, None])

    assert distribution == {
        "samples": 3,
        "missing_samples": 1,
        "average": 20.0,
        "median_p50": 20.0,
        "p95": 30.0,
        "minimum": 10.0,
        "maximum": 30.0,
    }


def test_metric_statistics_include_latency_and_tokens():
    metrics = calculate_metric_statistics(
        [
            _result("Q01", 100, 20, 70, 100, 10),
            _result("Q02", 200, 40, 140, 200, None),
        ]
    )

    assert metrics["total_latency_ms"]["average"] == 150.0
    assert metrics["retrieval_latency_ms"]["median_p50"] == 30.0
    assert metrics["openai_generation_latency_ms"]["maximum"] == 140.0
    assert metrics["input_tokens"]["average"] == 150.0
    assert metrics["output_tokens"]["samples"] == 1
    assert metrics["output_tokens"]["missing_samples"] == 1


def test_latency_shares_use_aggregate_time_from_complete_requests():
    shares = calculate_latency_shares(
        [
            _result("Q01", 100, 20, 70),
            _result("Q02", 300, 100, 180),
        ]
    )

    assert shares["samples"] == 2
    assert shares["retrieval_percentage"] == pytest.approx(30.0)
    assert shares["openai_generation_percentage"] == pytest.approx(62.5)
    assert shares["other_percentage"] == pytest.approx(7.5)


def test_outlier_detection_uses_total_latency_iqr():
    results = [
        _result("Q01", 100, 20, 70),
        _result("Q02", 105, 20, 75),
        _result("Q03", 110, 25, 75),
        _result("Q04", 115, 25, 80),
        _result("Q05", 500, 50, 440),
    ]

    analysis = detect_total_latency_outliers(results)

    assert analysis["threshold_ms"] == pytest.approx(130.0)
    assert [item["question_id"] for item in analysis["outliers"]] == ["Q05"]


def test_slowest_requests_are_selected_from_p95_threshold():
    results = [
        _result(f"Q{index:02}", index, 1, 1)
        for index in range(1, 21)
    ]

    assert [item["question_id"] for item in slowest_at_p95(results)] == [
        "Q20",
        "Q19",
    ]


def test_request_report_excludes_question_chunks_and_answer():
    result = _safe_request_result(
        question_id="Q01",
        repetition=1,
        http_status=200,
        observation={
            "request_id": "request-Q01",
            "endpoint": "/chat/document",
            "status": "success",
            "total_latency_ms": 100,
            "retrieval_latency_ms": 20,
            "openai_generation_latency_ms": 70,
            "input_tokens": 100,
            "output_tokens": 20,
            "question": "sensitive question",
            "chunks": ["sensitive chunk"],
            "answer": "sensitive answer",
        },
    )

    assert "question" not in result
    assert "chunks" not in result
    assert "answer" not in result
