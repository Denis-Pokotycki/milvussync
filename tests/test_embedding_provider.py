import pytest
import openai

from sync.embeddings.openai_provider import OpenAIEmbeddingProvider


def _make_provider():
    return OpenAIEmbeddingProvider(api_key="sk-test", model="text-embedding-ada-002")


def _fake_response(vector):
    return {"data": [{"embedding": vector}]}


def test_embed_returns_list(monkeypatch):
    provider = _make_provider()
    vector = [0.1, 0.2, 0.3]
    monkeypatch.setattr(
        openai.Embedding,
        "create",
        lambda **kwargs: _fake_response(vector),
    )
    result = provider.embed("Road works contract")
    assert result == vector


def test_embed_empty_string(monkeypatch):
    provider = _make_provider()
    monkeypatch.setattr(
        openai.Embedding,
        "create",
        lambda **kwargs: _fake_response([0.0, 0.0]),
    )
    result = provider.embed("")
    assert isinstance(result, list)


def test_embed_retries_on_rate_limit(monkeypatch):
    provider = _make_provider()
    call_count = 0
    vector = [0.5, 0.5]

    def _flaky(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise openai.error.RateLimitError("too many requests")
        return _fake_response(vector)

    monkeypatch.setattr(openai.Embedding, "create", _flaky)
    result = provider.embed("test")
    assert result == vector
    assert call_count == 3


def test_embed_exhausted_retries_raises(monkeypatch):
    provider = _make_provider()
    monkeypatch.setattr(
        openai.Embedding,
        "create",
        lambda **kwargs: (_ for _ in ()).throw(
            openai.error.RateLimitError("rate limit")
        ),
    )
    with pytest.raises(openai.error.RateLimitError):
        provider.embed("test")


def test_embed_auth_error_does_not_retry(monkeypatch):
    provider = _make_provider()
    call_count = 0

    def _auth_fail(**kwargs):
        nonlocal call_count
        call_count += 1
        raise openai.error.AuthenticationError("bad key")

    monkeypatch.setattr(openai.Embedding, "create", _auth_fail)
    with pytest.raises(openai.error.AuthenticationError):
        provider.embed("test")

    assert call_count == 1  # No retry for auth errors
