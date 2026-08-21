from __future__ import annotations

import argparse
import inspect
import json
import re
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable

from app.services import vector_db_service
from app.services.document_service import (
    calculate_file_hash,
    extract_pages_from_pdf,
    generate_embeddings,
    split_pages,
    validate_pdf,
)
from app.services.vector_db_service import (
    configure_vector_db,
    count_document_chunks,
    find_document_by_hash,
    get_collection,
    save_chunks,
    search_similar_chunks_with_metadata,
)


EVALUATION_DIR = Path(__file__).resolve().parent
DEFAULT_PDF_PATH = EVALUATION_DIR / "data" / "NovaTech_Manual_Operativo.pdf"
DEFAULT_GROUND_TRUTH_PATH = (
    EVALUATION_DIR / "data" / "RAG_Ground_Truth_con_paginas.md"
)
DEFAULT_RESULTS_PATH = EVALUATION_DIR / "results" / "baseline_results.json"

RETRIEVAL_SIGNATURE = inspect.signature(search_similar_chunks_with_metadata)
N_RESULTS = RETRIEVAL_SIGNATURE.parameters["n_results"].default
MAX_DISTANCE = RETRIEVAL_SIGNATURE.parameters["max_distance"].default
SPLIT_SIGNATURE = inspect.signature(split_pages)
CHUNK_SIZE = SPLIT_SIGNATURE.parameters["chunk_size"].default
OVERLAP = SPLIT_SIGNATURE.parameters["overlap"].default

FIELD_ALIASES = {
    "pregunta": "question",
    "respuesta esperada": "expected_answer",
    "seccion": "section",
    "seccin": "section",
    "pagina pdf esperada": "expected_page",
    "pgina pdf esperada": "expected_page",
    "evidencia": "evidence",
    "dificultad": "difficulty",
    "categoria": "category",
    "categora": "category",
}
REQUIRED_FIELDS = {
    "question",
    "expected_answer",
    "section",
    "expected_page",
    "evidence",
    "difficulty",
    "category",
}

RetrievalFunction = Callable[..., list[dict]]


@dataclass(frozen=True)
class BenchmarkQuestion:
    question_id: str
    question: str
    expected_answer: str
    section: str
    expected_page: int
    evidence: str
    difficulty: str
    category: str


def _normalize_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_label).strip().lower()


def parse_ground_truth_text(markdown: str) -> list[BenchmarkQuestion]:
    question_headers = list(
        re.finditer(r"^###\s+(Q\d+)\s*$", markdown, flags=re.MULTILINE)
    )
    if not question_headers:
        raise ValueError("El Ground Truth no contiene preguntas con formato '### QNN'.")

    questions: list[BenchmarkQuestion] = []
    for index, header in enumerate(question_headers):
        block_end = (
            question_headers[index + 1].start()
            if index + 1 < len(question_headers)
            else len(markdown)
        )
        block = markdown[header.end() : block_end]
        fields: dict[str, str] = {}
        field_headers = list(
            re.finditer(
                r"^\*\*(.+?):\*\*[ \t]*(.*)$",
                block,
                flags=re.MULTILINE,
            )
        )

        for field_index, field_header in enumerate(field_headers):
            normalized_label = _normalize_label(field_header.group(1))
            canonical_name = FIELD_ALIASES.get(normalized_label)
            if canonical_name is None:
                continue

            value_end = (
                field_headers[field_index + 1].start()
                if field_index + 1 < len(field_headers)
                else len(block)
            )
            following_lines = block[field_header.end() : value_end]
            value = "\n".join(
                part
                for part in (field_header.group(2).strip(), following_lines.strip())
                if part
            )
            value = re.split(r"^---\s*$", value, maxsplit=1, flags=re.MULTILINE)[0]
            fields[canonical_name] = value.strip()

        missing_fields = sorted(REQUIRED_FIELDS - fields.keys())
        if missing_fields:
            raise ValueError(
                f"{header.group(1)} no contiene campos requeridos: "
                f"{', '.join(missing_fields)}."
            )

        page_match = re.fullmatch(r"\d+", fields["expected_page"])
        if page_match is None:
            raise ValueError(
                f"{header.group(1)} tiene una página esperada inválida: "
                f"{fields['expected_page']!r}."
            )

        questions.append(
            BenchmarkQuestion(
                question_id=header.group(1),
                question=fields["question"],
                expected_answer=fields["expected_answer"],
                section=fields["section"],
                expected_page=int(fields["expected_page"]),
                evidence=fields["evidence"],
                difficulty=fields["difficulty"],
                category=fields["category"],
            )
        )

    question_ids = [question.question_id for question in questions]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("El Ground Truth contiene IDs de pregunta duplicados.")

    return questions


def parse_ground_truth(path: Path) -> list[BenchmarkQuestion]:
    return parse_ground_truth_text(path.read_text(encoding="utf-8"))


def ingest_benchmark_pdf(pdf_path: Path) -> tuple[str, int, str]:
    with pdf_path.open("rb") as file_stream:
        upload = SimpleNamespace(
            file=file_stream,
            filename=pdf_path.name,
            content_type="application/pdf",
        )
        validate_pdf(upload)
        file_hash = calculate_file_hash(upload)
        document_id = find_document_by_hash(file_hash)

        if document_id is not None:
            return document_id, count_document_chunks(document_id), file_hash

        pages = extract_pages_from_pdf(upload)
        chunks = split_pages(pages)
        chunks_with_embeddings = generate_embeddings(chunks)
        document_id = save_chunks(chunks_with_embeddings, pdf_path.name, file_hash)

    return document_id, len(chunks), file_hash


def close_isolated_vector_db() -> None:
    client = vector_db_service._client
    if client is not None:
        client.close()
    configure_vector_db(str(EVALUATION_DIR / ".unused_chroma_db"))


def load_chunk_index_lookup(document_id: str) -> dict[tuple, int]:
    stored_chunks = get_collection().get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    lookup: dict[tuple, int] = {}

    for text, metadata in zip(
        stored_chunks.get("documents", []),
        stored_chunks.get("metadatas", []),
    ):
        if metadata is None or not isinstance(metadata.get("chunk_index"), int):
            continue
        key = (
            text,
            metadata.get("filename"),
            metadata.get("page_number"),
        )
        lookup[key] = metadata["chunk_index"]

    return lookup


def page_hit_at_k(expected_page: int, retrieved_pages: list, k: int) -> bool:
    if k < 1:
        raise ValueError("k debe ser mayor o igual que 1.")
    return expected_page in retrieved_pages[:k]


def reciprocal_rank(expected_page: int, retrieved_pages: list) -> float:
    for rank, page_number in enumerate(retrieved_pages, start=1):
        if page_number == expected_page:
            return 1.0 / rank
    return 0.0


def normalize_evidence_text(text: str) -> str:
    normalized = text.strip()
    quote_pairs = {'"': '"', "'": "'", "“": "”", "‘": "’"}
    if len(normalized) >= 2 and quote_pairs.get(normalized[0]) == normalized[-1]:
        normalized = normalized[1:-1]
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def evidence_segments(evidence: str) -> list[str]:
    normalized_evidence = normalize_evidence_text(evidence)
    segments = [
        segment.strip()
        for segment in re.split(r"(?:\.{3,}|…)", normalized_evidence)
        if segment.strip()
    ]
    if not segments:
        raise ValueError("La evidencia no contiene segmentos evaluables.")
    return segments


def chunk_contains_evidence(chunk_text: str, evidence: str) -> bool:
    normalized_chunk = normalize_evidence_text(chunk_text)
    return all(segment in normalized_chunk for segment in evidence_segments(evidence))


def evidence_hit_at_k(evidence: str, ranked_results: list[dict], k: int = 4) -> bool:
    if k < 1:
        raise ValueError("k debe ser mayor o igual que 1.")
    return any(
        chunk_contains_evidence(result["text"], evidence)
        for result in ranked_results[:k]
    )


def rank_retrieved_chunks(
    retrieved: list[dict],
    chunk_index_lookup: dict[tuple, int] | None = None,
) -> list[dict]:
    chunk_index_lookup = chunk_index_lookup or {}
    ranked_results: list[dict] = []

    for rank, item in enumerate(retrieved, start=1):
        lookup_key = (
            item.get("text"),
            item.get("filename"),
            item.get("page_number"),
        )
        ranked_result = {
            "rank": rank,
            "text": item.get("text", ""),
            "filename": item.get("filename"),
            "page_number": item.get("page_number"),
            "chunk_index": item.get(
                "chunk_index", chunk_index_lookup.get(lookup_key)
            ),
        }
        if "distance" in item:
            ranked_result["distance"] = item["distance"]
        ranked_results.append(ranked_result)

    return ranked_results


def build_question_result(
    question: BenchmarkQuestion,
    ranked_results: list[dict],
    *,
    page_ks: Iterable[int],
    evidence_ks: Iterable[int],
) -> dict:
    retrieved_pages = [item["page_number"] for item in ranked_results]
    first_rank = next(
        (
            item["rank"]
            for item in ranked_results
            if item["page_number"] == question.expected_page
        ),
        None,
    )
    result = asdict(question)
    result.update(
        {
            "retrieved_pages": retrieved_pages,
            "retrieved_results": ranked_results,
            "first_expected_page_rank": first_rank,
            "reciprocal_rank": reciprocal_rank(
                question.expected_page, retrieved_pages
            ),
        }
    )
    for k in page_ks:
        result[f"page_hit_at_{k}"] = page_hit_at_k(
            question.expected_page, retrieved_pages, k
        )
    for k in evidence_ks:
        result[f"evidence_hit_at_{k}"] = evidence_hit_at_k(
            question.evidence, ranked_results, k
        )
    return result


def evaluate_questions(
    questions: Iterable[BenchmarkQuestion],
    document_id: str,
    retrieval_function: RetrievalFunction = search_similar_chunks_with_metadata,
    chunk_index_lookup: dict[tuple, int] | None = None,
    n_results: int = N_RESULTS,
    max_distance: float = MAX_DISTANCE,
    evidence_ks: Iterable[int] = (4,),
) -> list[dict]:
    results: list[dict] = []

    for question in questions:
        retrieved = retrieval_function(
            question=question.question,
            n_results=n_results,
            document_id=document_id,
            max_distance=max_distance,
        )
        ranked_results = rank_retrieved_chunks(retrieved, chunk_index_lookup)
        results.append(
            build_question_result(
                question,
                ranked_results,
                page_ks=range(1, n_results + 1),
                evidence_ks=evidence_ks,
            )
        )

    return results


def calculate_metrics(results: Iterable[dict]) -> dict:
    result_list = list(results)
    total = len(result_list)
    metrics = {
        "questions": total,
        "mrr": (
            sum(result["reciprocal_rank"] for result in result_list) / total
            if total
            else 0.0
        ),
    }
    if not result_list:
        return metrics

    page_hit_keys = sorted(
        (key for key in result_list[0] if re.fullmatch(r"page_hit_at_\d+", key)),
        key=lambda key: int(key.rsplit("_", maxsplit=1)[1]),
    )
    for key in page_hit_keys:
        k = int(key.rsplit("_", maxsplit=1)[1])
        hit_count = sum(bool(result[key]) for result in result_list)
        metrics[f"page_hits_at_{k}"] = hit_count
        metrics[key] = hit_count / total if total else 0.0

    evidence_hit_keys = sorted(
        (
            key
            for key in result_list[0]
            if re.fullmatch(r"evidence_hit_at_\d+", key)
        ),
        key=lambda key: int(key.rsplit("_", maxsplit=1)[1]),
    )
    for key in evidence_hit_keys:
        k = int(key.rsplit("_", maxsplit=1)[1])
        evidence_hits = sum(bool(result[key]) for result in result_list)
        metrics[f"evidence_hits_at_{k}"] = evidence_hits
        metrics[f"evidence_misses_at_{k}"] = total - evidence_hits
        metrics[key] = evidence_hits / total if total else 0.0
    return metrics


def calculate_group_metrics(results: Iterable[dict], group_key: str) -> dict:
    grouped_results: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        grouped_results[result[group_key]].append(result)

    return {
        group: calculate_metrics(group_results)
        for group, group_results in grouped_results.items()
    }


def build_report(
    results: list[dict],
    *,
    pdf_path: Path,
    ground_truth_path: Path,
    file_hash: str,
    chunks_saved: int,
) -> dict:
    return {
        "configuration": {
            "n_results": N_RESULTS,
            "max_distance": MAX_DISTANCE,
            "chunk_size": CHUNK_SIZE,
            "overlap": OVERLAP,
            "retrieval_function": (
                "app.services.vector_db_service."
                "search_similar_chunks_with_metadata"
            ),
            "vector_database_isolation": "temporary_directory",
            "pdf_path": str(pdf_path.resolve()),
            "ground_truth_path": str(ground_truth_path.resolve()),
            "pdf_sha256": file_hash,
            "chunks_saved": chunks_saved,
        },
        "summary": calculate_metrics(results),
        "category_metrics": calculate_group_metrics(results, "category"),
        "difficulty_metrics": calculate_group_metrics(results, "difficulty"),
        "results": results,
    }


def print_report(report: dict) -> None:
    for result in report["results"]:
        page_status = "HIT" if result["page_hit_at_4"] else "MISS"
        evidence_status = "HIT" if result["evidence_hit_at_4"] else "MISS"
        print(
            f"{result['question_id']} | Page@4 {page_status} | "
            f"Evidence {evidence_status}"
        )
        print(f"Expected page: {result['expected_page']}")
        print(f"Retrieved pages: {result['retrieved_pages']}")
        print(f"Category: {result['category']}")
        print(f"Difficulty: {result['difficulty']}")
        print()

    summary = report["summary"]
    print("RAG RETRIEVAL BASELINE")
    print("======================")
    print()
    print(f"Questions: {summary['questions']}")
    for k in range(1, N_RESULTS + 1):
        print(f"Page Hit@{k}: {summary[f'page_hit_at_{k}']:.2%}")
    print(f"MRR: {summary['mrr']:.6f}")
    print(f"Evidence Hit@4: {summary['evidence_hit_at_4']:.2%}")

    print("\nBy category")
    print("-----------")
    _print_group_metrics(report["category_metrics"])

    print("\nBy difficulty")
    print("-------------")
    _print_group_metrics(report["difficulty_metrics"])

    evidence_misses = [
        result for result in report["results"] if not result["evidence_hit_at_4"]
    ]
    if evidence_misses:
        print("\nEVIDENCE MISSES")
        print("===============")
        for result in evidence_misses:
            _print_evidence_miss(result)


def _print_group_metrics(group_metrics: dict) -> None:
    for group, metrics in group_metrics.items():
        print(
            f"{group}: Page@1 {metrics['page_hit_at_1']:.2%} | "
            f"Page@2 {metrics['page_hit_at_2']:.2%} | "
            f"Page@3 {metrics['page_hit_at_3']:.2%} | "
            f"Page@4 {metrics['page_hit_at_4']:.2%} | "
            f"MRR {metrics['mrr']:.6f} | "
            f"Evidence@4 {metrics['evidence_hit_at_4']:.2%}"
        )


def _print_evidence_miss(result: dict) -> None:
    print(f"\n{result['question_id']} | Evidence MISS")
    print("\nQuestion:")
    print(result["question"])
    print("\nExpected page:")
    print(result["expected_page"])
    print("\nGround-truth evidence:")
    print(result["evidence"])
    print("\nRetrieved:")

    for retrieved in result["retrieved_results"]:
        print(f"\nRank {retrieved['rank']}")
        print(f"page={retrieved['page_number']}")
        print(f"chunk_index={retrieved['chunk_index']}")
        if "distance" in retrieved:
            print(f"distance={retrieved['distance']}")
        print(f"text={retrieved['text']}")


def run_evaluation(
    pdf_path: Path = DEFAULT_PDF_PATH,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH_PATH,
    results_path: Path = DEFAULT_RESULTS_PATH,
) -> dict:
    questions = parse_ground_truth(ground_truth_path)
    if len(questions) != 25:
        raise ValueError(
            f"El benchmark debe contener 25 preguntas; contiene {len(questions)}."
        )

    with tempfile.TemporaryDirectory(prefix="rag-baseline-") as database_path:
        configure_vector_db(database_path)
        try:
            document_id, chunks_saved, file_hash = ingest_benchmark_pdf(pdf_path)
            chunk_index_lookup = load_chunk_index_lookup(document_id)
            results = evaluate_questions(
                questions,
                document_id,
                chunk_index_lookup=chunk_index_lookup,
            )
        finally:
            # Chroma's client owns the SQLite handle on Windows. Closing it is
            # required before TemporaryDirectory can safely remove the store.
            close_isolated_vector_db()

    report = build_report(
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
    print_report(report)
    print(f"\nJSON: {results_path.resolve()}")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate current RAG ranking with page Hit@K, MRR, and Evidence Hit@4."
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
    run_evaluation(args.pdf, args.ground_truth, args.output)


if __name__ == "__main__":
    main()
