import pytest

from app.services.document_service import split_text


def test_split_text_returns_list_of_strings():
    text = "a" * 1_000

    chunks = split_text(
        text=text,
        chunk_size=500,
        overlap=100,
    )

    assert isinstance(chunks, list)
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_split_text_uses_overlap():
    text = "0123456789"

    chunks = split_text(
        text=text,
        chunk_size=5,
        overlap=2,
    )

    assert chunks == [
        "01234",
        "34567",
        "6789",
        "9",
    ]


def test_split_text_rejects_invalid_overlap():
    with pytest.raises(
        ValueError,
        match="overlap debe ser menor",
    ):
        split_text(
            text="Texto de prueba",
            chunk_size=100,
            overlap=100,
        )