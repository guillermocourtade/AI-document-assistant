import pytest

from evaluation.compare_retrieval import (
    average_context_chars,
    calculate_context_growth,
    evaluate_reranked_questions,
    rerank_candidates,
)
from evaluation.evaluate_retrieval import (
    BenchmarkQuestion,
    calculate_metrics,
    evaluate_questions,
)


def _question(expected_page: int = 13) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        question_id="Q01",
        question="Pregunta sobre renuncia",
        expected_answer="30 días",
        section="15.1",
        expected_page=expected_page,
        evidence="evidencia correcta",
        difficulty="Easy",
        category="Direct",
    )


def _retrieved_chunk(rank: int, *, evidence: bool = False) -> dict:
    return {
        "text": "evidencia correcta" if evidence else f"Chunk {rank}",
        "filename": "manual.pdf",
        "page_number": 13 if evidence else rank,
        "chunk_index": rank + 70,
    }


def test_top6_metrics_keep_evidence_at_4_separate_from_evidence_at_6():
    retrieved = [
        _retrieved_chunk(rank, evidence=rank == 6) for rank in range(1, 7)
    ]

    results = evaluate_questions(
        [_question()],
        "document-id",
        retrieval_function=lambda **_kwargs: retrieved,
        n_results=6,
        evidence_ks=(4, 6),
    )
    metrics = calculate_metrics(results)

    assert results[0]["page_hit_at_5"] is False
    assert results[0]["page_hit_at_6"] is True
    assert results[0]["evidence_hit_at_4"] is False
    assert results[0]["evidence_hit_at_6"] is True
    assert metrics["page_hit_at_6"] == 1.0
    assert metrics["evidence_hit_at_4"] == 0.0
    assert metrics["evidence_hit_at_6"] == 1.0


def test_rerank_candidates_preserves_vector_rank_and_selects_top_results():
    candidates = [
        {
            "rank": rank,
            "text": f"Chunk {rank}",
            "filename": "manual.pdf",
            "page_number": rank,
            "chunk_index": rank + 10,
        }
        for rank in range(1, 5)
    ]

    def fake_reranker(_question, passages):
        scores = {1: 0.1, 2: 0.8, 3: 0.3, 4: 0.9}
        for passage in passages:
            passage["score"] = scores[passage["id"]]
        return sorted(passages, key=lambda item: item["score"], reverse=True)

    final_results, all_reranked = rerank_candidates(
        "Pregunta", candidates, fake_reranker, final_size=2
    )

    assert [item["vector_rank"] for item in all_reranked] == [4, 2, 3, 1]
    assert [item["rank"] for item in all_reranked] == [1, 2, 3, 4]
    assert [item["chunk_index"] for item in final_results] == [14, 12]
    assert len(candidates) == 4


def test_reranked_evaluation_keeps_candidate_pool_separate_from_final_context():
    retrieved = [_retrieved_chunk(rank) for rank in range(1, 6)]
    retrieved[-1] = _retrieved_chunk(5, evidence=True)
    received = {}

    def fake_retrieval(**kwargs):
        received.update(kwargs)
        return retrieved

    def fake_reranker(_question, passages):
        for passage in passages:
            passage["score"] = 1.0 if passage["id"] == 5 else 0.1
        return sorted(passages, key=lambda item: item["score"], reverse=True)

    results, timing = evaluate_reranked_questions(
        [_question()],
        "document-id",
        {},
        fake_reranker,
        retrieval_function=fake_retrieval,
        candidate_pool_size=5,
        final_size=2,
    )

    assert received["n_results"] == 5
    assert received["max_distance"] == 1.2
    assert len(results[0]["candidate_results"]) == 5
    assert len(results[0]["reranked_candidates"]) == 5
    assert len(results[0]["retrieved_results"]) == 2
    assert results[0]["retrieved_results"][0]["vector_rank"] == 5
    assert results[0]["evidence_hit_at_2"] is True
    assert timing["total_seconds"] >= 0.0


def test_context_growth_calculation():
    assert calculate_context_growth(4, 6) == {
        "baseline_chunks": 4,
        "experiment_chunks": 6,
        "ratio": 1.5,
        "increase_percentage": 50.0,
    }


def test_average_context_chars_uses_only_requested_final_chunks():
    results = [
        {
            "retrieved_results": [
                {"text": "1234"},
                {"text": "12"},
                {"text": "ignored"},
            ]
        },
        {
            "retrieved_results": [
                {"text": "123456"},
                {"text": "12"},
            ]
        },
    ]

    assert average_context_chars(results, 2) == pytest.approx(7.0)
