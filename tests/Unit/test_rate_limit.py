from app.rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rejects_after_limit_and_recovers_after_window():
    limiter = SlidingWindowRateLimiter()

    assert limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=2,
        window_seconds=10,
        now=0,
    )
    assert limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=2,
        window_seconds=10,
        now=1,
    )
    assert not limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=2,
        window_seconds=10,
        now=2,
    )
    assert limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=2,
        window_seconds=10,
        now=10,
    )


def test_sliding_window_isolates_clients_and_buckets():
    limiter = SlidingWindowRateLimiter()

    assert limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=1,
        window_seconds=60,
        now=1,
    )
    assert not limiter.allow(
        bucket="chat",
        client_id="client-a",
        limit=1,
        window_seconds=60,
        now=2,
    )
    assert limiter.allow(
        bucket="chat",
        client_id="client-b",
        limit=1,
        window_seconds=60,
        now=2,
    )
    assert limiter.allow(
        bucket="upload",
        client_id="client-a",
        limit=1,
        window_seconds=60,
        now=2,
    )


def test_reset_clears_accumulated_requests():
    limiter = SlidingWindowRateLimiter()
    arguments = {
        "bucket": "chat",
        "client_id": "client-a",
        "limit": 1,
        "window_seconds": 60,
        "now": 1,
    }

    assert limiter.allow(**arguments)
    assert not limiter.allow(**arguments)

    limiter.reset()

    assert limiter.allow(**arguments)
