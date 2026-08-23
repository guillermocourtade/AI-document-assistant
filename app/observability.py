from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Iterator
from uuid import uuid4

from app.logger import log_event


@dataclass
class RagObservation:
    request_id: str
    endpoint: str
    total_latency_ms: float | None = None
    retrieval_latency_ms: float | None = None
    openai_generation_latency_ms: float | None = None
    chunks_retrieved: int = 0
    cited_source_ids: list[str] = field(default_factory=list)
    cited_pages: list[int] = field(default_factory=list)
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status: str = "success"
    error_type: str | None = None

    def as_log_fields(self) -> dict:
        fields = {
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "status": self.status,
            "total_latency_ms": self.total_latency_ms,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "openai_generation_latency_ms": (
                self.openai_generation_latency_ms
            ),
            "chunks_retrieved": self.chunks_retrieved,
            "cited_source_ids": self.cited_source_ids,
            "cited_pages": self.cited_pages,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

        if self.error_type is not None:
            fields["error_type"] = self.error_type

        return fields

    def record_generation(
        self,
        *,
        latency_ms: float,
        model: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.openai_generation_latency_ms = latency_ms
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


_current_rag_observation: ContextVar[RagObservation | None] = ContextVar(
    "current_rag_observation",
    default=None,
)


def current_rag_observation() -> RagObservation | None:
    return _current_rag_observation.get()


@contextmanager
def observe_rag_request(endpoint: str) -> Iterator[RagObservation]:
    observation = RagObservation(
        request_id=str(uuid4()),
        endpoint=endpoint,
    )
    context_token = _current_rag_observation.set(observation)
    started_at = perf_counter()

    try:
        yield observation
    except Exception as exception:
        observation.status = "error"
        observation.error_type = type(exception).__name__
        raise
    finally:
        observation.total_latency_ms = _milliseconds_since(started_at)
        log_event("rag_request_completed", **observation.as_log_fields())
        _current_rag_observation.reset(context_token)


def _milliseconds_since(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
