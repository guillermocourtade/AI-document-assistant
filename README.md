# AI Document Assistant

AI-powered document assistant built with FastAPI, OpenAI, ChromaDB and React.

Upload PDF documents, index their contents into a persistent vector database, and ask questions using a Retrieval-Augmented Generation (RAG) pipeline with page-aware retrieval and verifiable citations.

The project was built with a production-oriented approach: typed API contracts, isolated business logic, automated tests, retrieval evaluation, structured observability, security controls, Docker and persistent vector storage.

---

## Features

- PDF upload and validation
- Page-aware text extraction and chunking
- OpenAI embeddings
- Persistent vector storage with ChromaDB
- Retrieval-Augmented Generation (RAG)
- Document-specific and multi-document chat
- Source citations with page numbers
- Backend validation of model-generated citations
- Session-scoped SHA-256 document deduplication
- Per-browser-session document isolation
- Automatic document expiration and cleanup
- Retrieval debugging endpoint
- Reproducible retrieval and citation evaluation
- Structured JSON observability
- Rate limiting
- OpenAI timeout and concurrency control
- Prompt-injection defenses
- Docker support
- Persistent ChromaDB storage using Docker volumes
- React + TypeScript frontend
- Automated tests and CI

---

## Architecture

                    ┌─────────────────────┐
                    │   React Frontend    │
                    │ Vite + TypeScript   │
                    └──────────┬──────────┘
                               │ HTTP
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │       Routers       │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
     Document Service    OpenAI Service    Vector DB Service
             │                 │                 │
             │          Embeddings / LLM        │
             │                 │                 ▼
             │                 │             ChromaDB
             │                 │          Persistent Store
             └─────────────────┴─────────────────┘

Backend structure:

app/
├── config.py
├── logger.py
├── main.py
├── observability.py
├── rate_limit.py
├── exceptions/
│   ├── custom_exceptions.py
│   └── handlers.py
├── models/
│   └── message.py
├── routers/
│   ├── system.py
│   ├── chat.py
│   └── documents.py
└── services/
    ├── document_service.py
    ├── openai_service.py
    └── vector_db_service.py

frontend/
└── src/
    ├── api/
    ├── components/
    ├── hooks/
    ├── types/
    └── App.tsx

evaluation/
├── evaluate_citations.py
├── benchmark_latency.py
└── results/

tests/
├── conftest.py
├── unit/
└── integration/

Routers handle HTTP concerns and orchestration.

Services contain business logic and external integrations.

This keeps OpenAI, document processing and vector database logic isolated from the HTTP layer.

---

## How the RAG Pipeline Works

### 1. Document ingestion

PDF
 ↓
Validation
 ↓
SHA-256 deduplication
 ↓
Page-aware text extraction
 ↓
Chunking with overlap
 ↓
OpenAI embeddings
 ↓
ChromaDB

Each chunk keeps metadata such as:

document_id
filename
file_hash
chunk_index
page
page_number
session_id
created_at
expires_at

Chunks never cross page boundaries, which allows the system to preserve page-level provenance.

### 2. Retrieval

Question
 ↓
Question embedding
 ↓
ChromaDB similarity search
 ↓
Top-6 candidates
 ↓
Distance filtering
 ↓
Relevant chunks + metadata

Current production retrieval configuration:

Top-K: 6
max_distance: 1.2

These values were selected through evaluation rather than intuition.

### 3. Answer generation

Retrieved chunks are sent to the LLM as untrusted context.

The model returns a structured response containing:

answer
source_ids

The backend validates every returned source_id against the chunks that were actually retrieved.

Only validated sources are converted into visible citations such as:

[p. 13]

This prevents the model from creating arbitrary page citations.

---

## Retrieval Evaluation

The project includes a reproducible benchmark containing 25 questions with page-level and evidence-level ground truth.

Initial Top-4 retrieval achieved:

Page Hit@1: 92%
Page Hit@2: 96%
Page Hit@3: 100%
Page Hit@4: 100%
MRR: 0.953333
Evidence Hit@4: 96%

One failure revealed an important distinction:

Retrieving the correct page does not necessarily mean retrieving the chunk containing the correct evidence.

Analysis showed that the missing evidence chunk appeared at vector rank 6.

Changing retrieval from Top-4 to Top-6 produced:

Evidence Hit@6: 25/25 (100%)

without degrading Page Hit or MRR.

A FlashRank reranking experiment was also evaluated but rejected because it reduced overall retrieval quality.

This benchmark acts as a regression baseline for future retrieval changes.

---

## Citation Evaluation

Citations are evaluated independently from retrieval.

Current recorded benchmark:

Citation Hit: 25/25 (100%)

The evaluation checks that:

- the expected evidence was retrieved
- the expected page was available
- the model cited a valid retrieved source
- fabricated source IDs were rejected
- citations correspond to real retrieved evidence

Detailed evaluation results are stored under:

evaluation/results/

---

## Observability

Each RAG request produces a structured event containing operational metrics such as:

request_id
endpoint
status
total latency
retrieval latency
OpenAI latency
retrieved chunks
cited source IDs
cited pages
model
token usage

Sensitive content is intentionally excluded.

The logs do not store:

- user questions
- retrieved document text
- complete answers
- API keys
- environment variables
- filenames
- raw exception messages

---

## Performance Baseline

A reproducible 25-question latency benchmark produced:

Average total latency: ~2.34 s
p50: ~2.28 s
p95: ~3.17 s

Average retrieval: ~661 ms
Average OpenAI: ~1676 ms

Approximate latency distribution:

Retrieval: 28.3%
OpenAI: 71.7%

---

## Security & Hardening

Uploaded PDFs are checked for:

- MIME type
- maximum file size
- %PDF- binary signature
- successful parsing
- maximum page count

Default limits:

PDF_MAX_SIZE_BYTES=10485760
PDF_MAX_PAGES=100

Document access requires a UUID in the `X-Session-ID` header. Every list,
deduplication, existence check and retrieval query is scoped to that session.
Documents expire after `DOCUMENT_TTL_HOURS` (24 hours by default), and expired
chunks are cleaned before document and chat operations.

Retrieved document content is treated as untrusted data.

Trusted application instructions are separated from document content, and adversarial tests cover prompt-injection attempts.

Default rate limits:

/upload: 5 requests / 60 seconds
/chat and /chat/document: shared quota of 20 requests / 60 seconds

OpenAI protection:

OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=0
OPENAI_MAX_CONCURRENCY=4

---

## API

System:

GET /
GET /health
GET /about

Documents:

GET /documents
POST /upload

Chat:

POST /chat
POST /chat/document

Retrieval debugging:

POST /search

All document, retrieval and chat endpoints require:

X-Session-ID: <uuid>

Controlled API errors use:

{
  "error": {
    "code": "string",
    "message": "string"
  }
}

---

## Tech Stack

Backend:
- Python
- FastAPI
- Pydantic
- Uvicorn
- OpenAI API
- ChromaDB
- pypdf
- pytest

Frontend:
- React
- Vite
- TypeScript
- Tailwind CSS

Infrastructure:
- Docker
- Docker Compose
- GitHub Actions
- Persistent Docker volumes

---

## Environment Variables

Create a .env file based on .env.example.

Example:

OPENAI_API_KEY=your_api_key
ALLOWED_ORIGINS=http://localhost:5173
CHROMA_DB_PATH=./chroma_db
PDF_MAX_SIZE_BYTES=10485760
PDF_MAX_PAGES=100
RATE_LIMIT_WINDOW_SECONDS=60
UPLOAD_RATE_LIMIT_REQUESTS=5
CHAT_RATE_LIMIT_REQUESTS=20
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=0
OPENAI_MAX_CONCURRENCY=4
DOCUMENT_TTL_HOURS=24

Never commit the real .env file.

---

## Running Locally

Backend:

python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

Backend:
http://localhost:8000

Swagger:
http://localhost:8000/docs

Frontend:

cd frontend
npm install
npm run dev

Vite normally starts at:
http://localhost:5173

---

## Running with Docker

Build and start:

docker compose up --build

Detached:

docker compose up -d --build

Health check:

curl http://localhost:8000/health

Docker Compose stores ChromaDB in the named volume:

chroma_data

mounted at:

/app/chroma_db

with:

CHROMA_DB_PATH=/app/chroma_db

Documents and embeddings therefore survive container recreation.

docker compose down
docker compose up -d

WARNING:
docker compose down -v also deletes the persistent volume and therefore removes the stored ChromaDB data. Only use -v when deleting the vector database is intentional.

---

## Docker Build Optimization

The Docker build context was reduced from approximately 487 MB to 1.02 kB by using a strict .dockerignore allowlist and copying only the backend application into the image.

This prevents local artifacts such as .venv, frontend/node_modules, chroma_db, .env and evaluation data from entering the backend image.

---

## Testing

Run:

pytest

Last documented hardening baseline:

122 passing tests

Tests use temporary ChromaDB storage rather than the real persistent database.

---

## Engineering Decisions

### Top-K and chunk overlap

Adding chunk overlap changed vector ranking. Top-K and overlap therefore need to be evaluated together.

The final Top-6 configuration was selected using an evidence-level benchmark.

### Document deduplication

Duplicate PDFs previously polluted ChromaDB and caused near-identical chunks to dominate retrieval.

Documents are deduplicated by SHA-256 within each browser session. The same PDF
uploaded by a different session is stored independently and never reuses the
first session's document ID.

### Isolated test database

Tests use temporary ChromaDB storage instead of the application's persistent database.

### Verified citations

LLM-generated citations are not trusted directly.

The backend validates model-returned source IDs against retrieved chunks before exposing citations to the client.

### Persistent storage

ChromaDB state is stored in a Docker named volume instead of the container filesystem, separating application lifecycle from data lifecycle.

---

## Current Status

The project currently includes:

- Functional full-stack RAG application
- Page-aware document ingestion
- Persistent ChromaDB storage
- Evidence-based retrieval configuration
- Verified source citations
- Retrieval and citation benchmarks
- Structured observability
- PDF security validation
- Prompt-injection defenses
- Rate limiting
- OpenAI timeout and concurrency protection
- Automated testing and CI
- Dockerized backend
- Persistent Docker volume

The next major engineering milestone is a real production deployment.

This requires evaluating backend hosting, frontend hosting, HTTPS, secrets management, production persistence for ChromaDB, infrastructure-level limits and multi-worker implications for the current in-memory rate limiter.

The local Docker named volume should not automatically be considered the production persistence strategy.

---

## Future Improvements

- Production deployment
- Production-grade persistent vector storage strategy
- Shared rate limiting for multiple workers/replicas
- Alternative reranking experiments
- Hybrid search
- Query rewriting
- Retrieval quality monitoring
- Additional RAG evaluation datasets

Any retrieval change should be measured against the existing evaluation baseline before replacing the production configuration.

---

## What I Learned

This project focuses not only on integrating an LLM, but on the engineering problems around production RAG systems:

- defining and preserving contracts between layers
- debugging retrieval separately from generation
- evaluating evidence rather than only final answers
- understanding how chunking changes vector ranking
- preventing duplicate data from contaminating retrieval
- validating LLM-generated citations
- treating retrieved documents as untrusted input
- building reproducible RAG evaluations
- measuring latency before optimizing
- isolating tests from persistent application state
- separating container lifecycle from data persistence

---

## License

This project is currently intended for educational and portfolio purposes.
