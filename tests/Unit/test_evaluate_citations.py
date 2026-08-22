from evaluation.evaluate_citations import (
    calculate_citation_metrics,
    evaluate_citation_questions,
    extract_cited_pages,
)
from evaluation.evaluate_retrieval import BenchmarkQuestion
from app.services.openai_service import CitedAnswer


def _question(
    question_id: str,
    expected_page: int,
    evidence: str,
) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        question_id=question_id,
        question=f"Pregunta {question_id}",
        expected_answer="Respuesta esperada",
        section="Sección",
        expected_page=expected_page,
        evidence=evidence,
        difficulty="Easy",
        category="Direct",
    )


def test_extract_cited_pages_keeps_unique_real_page_numbers():
    assert extract_cited_pages(
        [
            {"page_number": 13},
            {"page_number": None},
            {"page_number": 13},
            {"page_number": 4},
        ]
    ) == [13, 4]


def test_evaluator_detects_hit_and_retrieval_evidence_wrong_citation():
    questions = [
        _question("Q01", expected_page=3, evidence="evidencia uno"),
        _question("Q02", expected_page=8, evidence="evidencia dos"),
    ]

    def fake_retrieval(*, question, **_kwargs):
        if question == "Pregunta Q01":
            return [
                {
                    "source_id": "S1",
                    "text": "Contiene evidencia uno.",
                    "filename": "manual.pdf",
                    "page_number": 3,
                    "chunk_index": 10,
                }
            ]
        return [
            {
                "source_id": "S1",
                "text": "Contiene evidencia dos.",
                "filename": "manual.pdf",
                "page_number": 8,
                "chunk_index": 20,
            },
            {
                "source_id": "S2",
                "text": "Fuente distractora.",
                "filename": "manual.pdf",
                "page_number": 5,
                "chunk_index": 21,
            },
        ]

    def fake_generation(question, _chunks):
        source_id = "S1" if question == "Pregunta Q01" else "S2"
        return CitedAnswer(
            answer=f"Respuesta [[{source_id}]].",
            source_ids=[source_id],
        )

    results = evaluate_citation_questions(
        questions,
        "document-id",
        retrieval_function=fake_retrieval,
        generation_function=fake_generation,
        progress_function=None,
    )
    metrics = calculate_citation_metrics(results)

    assert results[0]["citation_hit"] is True
    assert results[0]["cited_pages"] == [3]
    assert results[0]["answer"] == "Respuesta [p. 3]."

    assert results[1]["citation_hit"] is False
    assert results[1]["cited_pages"] == [5]
    assert results[1]["retrieval_evidence_hit"] is True
    assert results[1]["retrieval_evidence_but_wrong_citation"] is True
    assert results[1]["failure_reason"] == "llm_cited_other_source"

    assert metrics["citation_hits"] == 1
    assert metrics["citation_hit_percentage"] == 50.0
    assert metrics["failed_questions"] == ["Q02"]
    assert metrics["retrieval_evidence_but_wrong_citation"] == 1


def test_evaluator_records_generation_error_as_citation_miss():
    def failing_generation(_question, _chunks):
        raise RuntimeError("generation failed")

    results = evaluate_citation_questions(
        [_question("Q01", expected_page=3, evidence="evidencia")],
        "document-id",
        retrieval_function=lambda **_kwargs: [
            {
                "source_id": "S1",
                "text": "Contiene evidencia.",
                "filename": "manual.pdf",
                "page_number": 3,
                "chunk_index": 10,
            }
        ],
        generation_function=failing_generation,
        progress_function=None,
    )

    assert results[0]["citation_hit"] is False
    assert results[0]["failure_reason"] == "generation_error"
    assert results[0]["generation_error"] == {
        "type": "RuntimeError",
        "message": "generation failed",
    }
