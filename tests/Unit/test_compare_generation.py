import json

import pytest

from evaluation.compare_generation import (
    build_generation_report,
    calculate_context_chars,
    calculate_generation_statistics,
    classify_answer_change,
    normalize_answer,
    pair_retrieval_results,
    run_generation_comparison,
    serialize_generation_report,
)


def _retrieval_result(question_id: str, size: int) -> dict:
    return {
        "question_id": question_id,
        "question": f"Pregunta {question_id}",
        "expected_answer": "Respuesta esperada",
        "section": "1.1",
        "expected_page": 1,
        "evidence": "evidencia",
        "difficulty": "Easy",
        "category": "Direct",
        "retrieved_pages": list(range(1, size + 1)),
        "retrieved_results": [
            {
                "rank": rank,
                "text": "x" * rank,
                "filename": "manual.pdf",
                "page_number": rank,
                "chunk_index": rank + 10,
            }
            for rank in range(1, size + 1)
        ],
        "first_expected_page_rank": 1,
        "reciprocal_rank": 1.0,
        f"evidence_hit_at_{size}": True,
    }


def _comparison_result(question_id: str, status: str) -> dict:
    error = {"type": "Error", "message": "failure"} if status == "ERROR" else None
    return {
        "question_id": question_id,
        "comparison_status": status,
        "top4": {
            "context_chars": 10,
            "generation_seconds": 1.0,
            "error": error,
        },
        "top6": {
            "context_chars": 15,
            "generation_seconds": 2.0,
            "error": error,
        },
    }


def test_answer_is_unchanged_after_whitespace_normalization():
    assert normalize_answer("  treinta\n días  ") == "treinta días"
    assert classify_answer_change("treinta\n días", "treinta   días") == "UNCHANGED"


def test_answer_is_changed_when_non_whitespace_content_differs():
    assert classify_answer_change("30 días.", "Treinta días.") == "CHANGED"


def test_context_chars_sums_exact_text_passed_to_generation():
    chunks = [{"text": "1234"}, {"text": "12"}, {"text": ""}]
    assert calculate_context_chars(chunks) == 6


def test_changed_and_unchanged_statistics_are_calculated_separately():
    statistics = calculate_generation_statistics(
        [
            _comparison_result("Q01", "CHANGED"),
            _comparison_result("Q02", "UNCHANGED"),
            _comparison_result("Q03", "ERROR"),
        ]
    )

    assert statistics["different_answers"] == 1
    assert statistics["identical_answers"] == 1
    assert statistics["changed_questions"] == ["Q01"]
    assert statistics["uncomparable_questions"] == ["Q03"]
    assert statistics["generation_errors"] == 2
    assert statistics["context"]["top4_average_chars"] == 10
    assert statistics["context"]["top6_average_chars"] == 15
    assert statistics["context"]["growth_percentage"] == pytest.approx(50.0)
    assert statistics["generation_timing"]["top4_total_seconds"] == 3.0
    assert statistics["generation_timing"]["top6_total_seconds"] == 6.0


def test_runner_calls_generation_in_interleaved_order_without_real_openai():
    top4_q1 = _retrieval_result("Q01", 4)
    top6_q1 = _retrieval_result("Q01", 6)
    top4_q2 = _retrieval_result("Q02", 4)
    top6_q2 = _retrieval_result("Q02", 6)
    calls = []

    def fake_generation(question, chunks):
        calls.append((question, len(chunks)))
        return f"respuesta con {len(chunks)} chunks"

    results = run_generation_comparison(
        [(top4_q1, top6_q1), (top4_q2, top6_q2)],
        generation_function=fake_generation,
        progress_function=None,
    )

    assert calls == [
        ("Pregunta Q01", 4),
        ("Pregunta Q01", 6),
        ("Pregunta Q02", 4),
        ("Pregunta Q02", 6),
    ]
    assert [result["comparison_status"] for result in results] == [
        "CHANGED",
        "CHANGED",
    ]


def test_retrieval_pairing_validates_top4_is_exact_top6_prefix():
    top4 = _retrieval_result("Q01", 4)
    top6 = _retrieval_result("Q01", 6)

    pairs = pair_retrieval_results(
        {"results": [top4]}, {"results": [top6]}, expected_question_count=1
    )

    assert pairs == [(top4, top6)]


def test_generation_report_serialization_preserves_unicode_and_results(tmp_path):
    result = _comparison_result("Q01", "UNCHANGED")
    result.update(
        {
            "question": "¿Cuántos días?",
            "expected_answer": "30 días",
        }
    )
    report = build_generation_report([result])
    output_path = tmp_path / "generation.json"

    serialize_generation_report(report, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert loaded["experiment"] == "generation_top4_vs_top6"
    assert loaded["results"][0]["question"] == "¿Cuántos días?"
    assert loaded["summary"]["identical_answers"] == 1
