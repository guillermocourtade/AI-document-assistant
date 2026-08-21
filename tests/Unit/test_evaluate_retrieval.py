import pytest

from evaluation.evaluate_retrieval import (
    BenchmarkQuestion,
    calculate_group_metrics,
    calculate_metrics,
    chunk_contains_evidence,
    evidence_hit_at_k,
    evaluate_questions,
    page_hit_at_k,
    parse_ground_truth_text,
    reciprocal_rank,
)


GROUND_TRUTH = """
### Q01

**Pregunta:**
¿Pregunta uno?

**Respuesta esperada:**
Respuesta uno.

**Sección:**
1. Sección

**Página PDF esperada:** 3

**Evidencia:**
"Evidencia uno"

**Dificultad:** Easy

**Categoría:** Direct

---

### Q02

**Pregunta:**
¿Pregunta dos?

**Respuesta esperada:**
Respuesta dos.

**Sección:**
2. Sección

**Página PDF esperada:** 8

**Evidencia:**
"Evidencia dos"

**Dificultad:** Hard

**Categoría:** Similar Sections
"""


def _question(
    question_id: str = "Q01",
    expected_page: int = 3,
    difficulty: str = "Easy",
    category: str = "Direct",
) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        question_id=question_id,
        question="Pregunta",
        expected_answer="Respuesta",
        section="Sección",
        expected_page=expected_page,
        evidence="Evidencia",
        difficulty=difficulty,
        category=category,
    )


def test_parse_ground_truth_reads_all_fields():
    questions = parse_ground_truth_text(GROUND_TRUTH)

    assert questions == [
        BenchmarkQuestion(
            question_id="Q01",
            question="¿Pregunta uno?",
            expected_answer="Respuesta uno.",
            section="1. Sección",
            expected_page=3,
            evidence='"Evidencia uno"',
            difficulty="Easy",
            category="Direct",
        ),
        BenchmarkQuestion(
            question_id="Q02",
            question="¿Pregunta dos?",
            expected_answer="Respuesta dos.",
            section="2. Sección",
            expected_page=8,
            evidence='"Evidencia dos"',
            difficulty="Hard",
            category="Similar Sections",
        ),
    ]


def test_evaluate_questions_preserves_ranking_and_calculates_metrics():
    def fake_retrieval(**_kwargs):
        return [
            {
                "text": "Chunk irrelevante",
                "page_number": 5,
                "filename": "manual.pdf",
                "distance": 0.4,
            },
            {
                "text": "Otro chunk",
                "page_number": 8,
                "filename": "manual.pdf",
            },
            {
                "text": "Este chunk contiene Evidencia",
                "page_number": 3,
                "filename": "manual.pdf",
            },
        ]

    results = evaluate_questions(
        [_question()],
        "document-id",
        retrieval_function=fake_retrieval,
        chunk_index_lookup={
            ("Este chunk contiene Evidencia", "manual.pdf", 3): 42
        },
    )

    assert results[0]["retrieved_pages"] == [5, 8, 3]
    assert results[0]["retrieved_results"] == [
        {
            "rank": 1,
            "text": "Chunk irrelevante",
            "filename": "manual.pdf",
            "page_number": 5,
            "chunk_index": None,
            "distance": 0.4,
        },
        {
            "rank": 2,
            "text": "Otro chunk",
            "filename": "manual.pdf",
            "page_number": 8,
            "chunk_index": None,
        },
        {
            "rank": 3,
            "text": "Este chunk contiene Evidencia",
            "filename": "manual.pdf",
            "page_number": 3,
            "chunk_index": 42,
        },
    ]
    assert results[0]["page_hit_at_1"] is False
    assert results[0]["page_hit_at_2"] is False
    assert results[0]["page_hit_at_3"] is True
    assert results[0]["page_hit_at_4"] is True
    assert results[0]["first_expected_page_rank"] == 3
    assert results[0]["reciprocal_rank"] == pytest.approx(1 / 3)
    assert results[0]["evidence_hit_at_4"] is True


@pytest.mark.parametrize(
    ("k", "expected_hit"),
    [(1, False), (2, False), (3, True), (4, True)],
)
def test_page_hit_at_k_uses_only_first_k_results(k, expected_hit):
    assert page_hit_at_k(13, [5, 8, 13, 4], k) is expected_hit


@pytest.mark.parametrize(
    ("pages", "expected_reciprocal_rank"),
    [([13, 5, 8, 4], 1.0), ([5, 13, 8, 4], 0.5), ([5, 8, 13, 4], 1 / 3), ([5, 8, 4], 0.0)],
)
def test_reciprocal_rank_uses_first_expected_page(
    pages, expected_reciprocal_rank
):
    assert reciprocal_rank(13, pages) == pytest.approx(expected_reciprocal_rank)


def test_calculate_metrics_computes_hit_at_k_mrr_and_evidence_hit():
    metrics = calculate_metrics(
        [
            {
                "page_hit_at_1": True,
                "page_hit_at_2": True,
                "page_hit_at_3": True,
                "page_hit_at_4": True,
                "reciprocal_rank": 1.0,
                "evidence_hit_at_4": True,
            },
            {
                "page_hit_at_1": False,
                "page_hit_at_2": False,
                "page_hit_at_3": True,
                "page_hit_at_4": True,
                "reciprocal_rank": 1 / 3,
                "evidence_hit_at_4": False,
            },
            {
                "page_hit_at_1": False,
                "page_hit_at_2": False,
                "page_hit_at_3": False,
                "page_hit_at_4": False,
                "reciprocal_rank": 0.0,
                "evidence_hit_at_4": True,
            },
        ]
    )

    assert metrics["questions"] == 3
    assert metrics["page_hit_at_1"] == pytest.approx(1 / 3)
    assert metrics["page_hit_at_2"] == pytest.approx(1 / 3)
    assert metrics["page_hit_at_3"] == pytest.approx(2 / 3)
    assert metrics["page_hit_at_4"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == pytest.approx(4 / 9)
    assert metrics["evidence_hits_at_4"] == 2
    assert metrics["evidence_misses_at_4"] == 1
    assert metrics["evidence_hit_at_4"] == pytest.approx(2 / 3)


def test_evidence_hit_exact():
    assert chunk_contains_evidence(
        "El chunk contiene la evidencia necesaria para responder.",
        '"la evidencia necesaria"',
    )


def test_evidence_hit_normalizes_whitespace():
    assert chunk_contains_evidence(
        "La evidencia\n   necesaria\t está aquí.",
        '"la evidencia necesaria está aquí"',
    )


def test_evidence_hit_supports_ellipsis_segments_in_same_chunk():
    assert chunk_contains_evidence(
        "Debe presentar su reporte de gastos, junto con comprobantes, "
        "dentro de los siguientes 7 días hábiles.",
        '"debe presentar su reporte de gastos... dentro de los siguientes '
        '7 días hábiles"',
    )


def test_evidence_miss_when_segments_are_split_across_chunks():
    assert not evidence_hit_at_k(
        "protocolo de escalamiento... sin aprobación previa",
        [
            {"text": "Debe iniciar el protocolo de escalamiento."},
            {"text": "Puede actuar sin aprobación previa."},
        ],
    )


def test_calculate_group_metrics_groups_categories():
    metrics = calculate_group_metrics(
        [
            _metric_result("category", "Direct", rank=1, evidence_hit=True),
            _metric_result("category", "Direct", rank=None, evidence_hit=False),
            _metric_result("category", "Paraphrase", rank=2, evidence_hit=True),
        ],
        "category",
    )

    assert metrics["Direct"]["page_hit_at_1"] == 0.5
    assert metrics["Direct"]["page_hit_at_4"] == 0.5
    assert metrics["Direct"]["mrr"] == 0.5
    assert metrics["Direct"]["evidence_hit_at_4"] == 0.5
    assert metrics["Paraphrase"]["page_hit_at_2"] == 1.0
    assert metrics["Paraphrase"]["mrr"] == 0.5


def test_calculate_group_metrics_groups_difficulties():
    metrics = calculate_group_metrics(
        [
            _metric_result("difficulty", "Easy", rank=1, evidence_hit=True),
            _metric_result("difficulty", "Hard", rank=None, evidence_hit=False),
            _metric_result("difficulty", "Hard", rank=3, evidence_hit=True),
        ],
        "difficulty",
    )

    assert metrics["Easy"]["page_hit_at_1"] == 1.0
    assert metrics["Easy"]["evidence_hit_at_4"] == 1.0
    assert metrics["Hard"]["page_hit_at_2"] == 0.0
    assert metrics["Hard"]["page_hit_at_3"] == 0.5
    assert metrics["Hard"]["mrr"] == pytest.approx(1 / 6)


def _metric_result(group_key, group, rank, evidence_hit):
    result = {
        group_key: group,
        "reciprocal_rank": 1 / rank if rank else 0.0,
        "evidence_hit_at_4": evidence_hit,
    }
    for k in range(1, 5):
        result[f"page_hit_at_{k}"] = rank is not None and rank <= k
    return result
