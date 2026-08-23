import json
import logging

import pytest

from app.logger import JsonFormatter
from app.observability import observe_rag_request


def test_json_formatter_serializes_structured_fields():
    record = logging.LogRecord(
        name="ai_document_assistant",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="rag_request_completed",
        args=(),
        exc_info=None,
    )
    record.structured_data = {
        "request_id": "request-123",
        "chunks_retrieved": 2,
    }

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "rag_request_completed"
    assert payload["request_id"] == "request-123"
    assert payload["chunks_retrieved"] == 2


def test_observation_logs_only_explicit_safe_fields(monkeypatch):
    logged_events = []
    times = iter([10.0, 10.125])

    monkeypatch.setattr(
        "app.observability.perf_counter",
        lambda: next(times),
    )
    monkeypatch.setattr(
        "app.observability.uuid4",
        lambda: "request-123",
    )
    monkeypatch.setattr(
        "app.observability.log_event",
        lambda event, **fields: logged_events.append((event, fields)),
    )

    with observe_rag_request("/chat") as observation:
        observation.retrieval_latency_ms = 20.0
        observation.openai_generation_latency_ms = 80.0
        observation.chunks_retrieved = 2
        observation.cited_source_ids = ["S2"]
        observation.cited_pages = [7]
        observation.model = "gpt-test"
        observation.input_tokens = 100
        observation.output_tokens = 25

    event, fields = logged_events[0]
    serialized = json.dumps(fields)

    assert event == "rag_request_completed"
    assert fields == {
        "request_id": "request-123",
        "endpoint": "/chat",
        "status": "success",
        "total_latency_ms": 125.0,
        "retrieval_latency_ms": 20.0,
        "openai_generation_latency_ms": 80.0,
        "chunks_retrieved": 2,
        "cited_source_ids": ["S2"],
        "cited_pages": [7],
        "model": "gpt-test",
        "input_tokens": 100,
        "output_tokens": 25,
    }
    assert "question" not in serialized
    assert "answer" not in serialized
    assert "content" not in serialized
    assert "api_key" not in serialized


def test_observation_marks_failed_requests(monkeypatch):
    logged_events = []

    monkeypatch.setattr(
        "app.observability.log_event",
        lambda event, **fields: logged_events.append(fields),
    )

    with pytest.raises(RuntimeError):
        with observe_rag_request("/chat/document"):
            raise RuntimeError("sensitive detail")

    assert logged_events[0]["status"] == "error"
    assert logged_events[0]["error_type"] == "RuntimeError"
    assert "sensitive detail" not in json.dumps(logged_events[0])
