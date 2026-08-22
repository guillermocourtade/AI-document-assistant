# Retrieval baseline evaluation

This tool measures page-level `Hit@1` through the current retrieval Top-K, mean
reciprocal rank (`MRR`), and deterministic `Evidence Hit@4` for the retrieval
implementation. It does not call answer generation or use an LLM to judge
answers.

Run it from the repository root with the existing virtual environment activated:

```bash
python -m evaluation.evaluate_retrieval
```

The command:

1. parses the 25 questions in `data/RAG_Ground_Truth_con_paginas.md`;
2. creates a temporary, isolated ChromaDB directory;
3. ingests `data/NovaTech_Manual_Operativo.pdf` through the production PDF,
   chunking, embedding, SHA-256 deduplication, and persistence functions;
4. calls the production `search_similar_chunks_with_metadata` function with its
   current `n_results=6` and `max_distance=1.2` defaults;
5. enriches returned chunks with their already-persisted `chunk_index` metadata;
6. calculates ranking and evidence metrics; and
7. writes `results/baseline_results.json`.

A page hit at K is exactly
`expected_page in retrieved_pages[:K]`. Reciprocal rank is `1 / rank` for the
first occurrence of the expected page, or zero when absent. MRR is the mean of
the per-question reciprocal ranks.

For Evidence Hit, surrounding quotes are removed, whitespace is collapsed, and
text is case-folded. Ground-truth evidence containing `...` or `…` is split into
non-empty segments. A hit requires every segment to occur in the same one of the
first four chunks. Evidence is never combined across chunks.

The persisted user database at `./chroma_db` is never cleared or used by this
command.

The stored baseline and Day 24 result files remain historical artifacts of the
Top-4 versus Top-6 experiments; changing the production default does not rewrite
those results.

The production retrieval function does not expose distances in its structured
return value, so the evaluator does not record them. The persisted metadata does
contain `chunk_index`; the evaluator attaches it by exact text, filename, and page
matching without issuing another vector query. Adding distances would require a
change to production retrieval, which is intentionally frozen for this baseline.

## Day 24 comparison experiment

Install the evaluation-only dependency and run the A/B comparison:

```bash
python -m pip install -r evaluation/requirements-experiments.txt
python -m evaluation.compare_retrieval
```

The experiment compares the unchanged vector Top-4 baseline, vector Top-6, and
vector Top-10 reranked to four final chunks. Reranking uses FlashRank 0.2.10 with
the multilingual `ms-marco-MultiBERT-L-12` cross-encoder on ONNX CPU. Its model
cache defaults to the operating-system temporary directory; no model is written
to the repository. The benchmark ChromaDB remains temporary and isolated.

## Top-4 vs Top-6 generation experiment

Run the final generation comparison with:

```bash
python -m evaluation.compare_generation
```

The runner reuses the frozen, full retrieval outputs in
`results/day24_baseline_results.json` and `results/top6_results.json`, validates
that every Top-4 is the exact prefix of its Top-6, and then calls the unchanged
production `generate_response()` function 50 times. Calls are interleaved as
Top-4 then Top-6 for each of the 25 questions. Reusing retrieval isolates the
generation comparison from embedding or vector-database drift.

Answers are marked `UNCHANGED` only when they are exactly equal after whitespace
normalization. The complete answers, retrieval metadata, context sizes, errors,
and generation timings are written to
`results/generation_top4_vs_top6.json`.

## End-to-end citation evaluation

Run the citation benchmark with:

```bash
python -m evaluation.evaluate_citations
```

This evaluator reuses the same 25-question Ground Truth and isolated benchmark
ingestion. For every question it runs production retrieval, structured answer
generation, and the router's source-ID validation/page mapping. A Citation Hit
means that at least one final cited page equals `expected_page`. The report also
checks whether the exact Ground Truth evidence was present in a chunk sent to
generation; a citation miss is classified separately as
`llm_cited_other_source` when that evidence was available but the final answer
cited only other pages.

The complete retrieval context, raw model source IDs, validated source IDs,
final answer, final sources, failure diagnostics, and aggregate metrics are
written to `results/citation_results.json`. The persisted `./chroma_db` is not
used or modified.
