import pytest

from app.config import _origins_from_env, _positive_int_from_env


DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def test_allowed_origins_uses_defaults_when_env_is_not_defined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    origins = _origins_from_env("ALLOWED_ORIGINS", DEFAULT_ORIGINS)

    assert origins == DEFAULT_ORIGINS
    assert origins is not DEFAULT_ORIGINS


def test_allowed_origins_accepts_one_configured_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://frontend.example.com",
    )

    origins = _origins_from_env("ALLOWED_ORIGINS", DEFAULT_ORIGINS)

    assert origins == ["https://frontend.example.com"]


def test_allowed_origins_accepts_multiple_comma_separated_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://one.example.com,https://two.example.com",
    )

    origins = _origins_from_env("ALLOWED_ORIGINS", DEFAULT_ORIGINS)

    assert origins == [
        "https://one.example.com",
        "https://two.example.com",
    ]


def test_allowed_origins_strips_spaces_and_ignores_empty_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        " , https://one.example.com, ,https://two.example.com , ",
    )

    origins = _origins_from_env("ALLOWED_ORIGINS", DEFAULT_ORIGINS)

    assert origins == [
        "https://one.example.com",
        "https://two.example.com",
    ]


def test_allowed_origins_rejects_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="no puede contener"):
        _origins_from_env("ALLOWED_ORIGINS", DEFAULT_ORIGINS)


def test_document_ttl_hours_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCUMENT_TTL_HOURS", raising=False)

    assert _positive_int_from_env("DOCUMENT_TTL_HOURS", 24) == 24


def test_document_ttl_hours_can_be_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCUMENT_TTL_HOURS", "12")

    assert _positive_int_from_env("DOCUMENT_TTL_HOURS", 24) == 12


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_document_ttl_hours_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("DOCUMENT_TTL_HOURS", value)

    with pytest.raises(RuntimeError, match="entero positivo"):
        _positive_int_from_env("DOCUMENT_TTL_HOURS", 24)
