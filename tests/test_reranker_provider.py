"""Tests for BGERerankerProvider — mocks CrossEncoder so no model download."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from sync.embeddings.reranker_provider import BGERerankerProvider


@pytest.fixture
def mock_model():
    model = MagicMock()
    return model


@pytest.fixture
def provider(mock_model):
    p = BGERerankerProvider(model_name="fake-reranker")
    p._model = mock_model
    return p


def _records(*titles):
    return [{"pk": f"T00{i}_en", "title": t, "language_code": "en"} for i, t in enumerate(titles)]


def test_rerank_returns_records_with_rerank_score(provider, mock_model):
    mock_model.predict.return_value = np.array([0.9, 0.3])
    records = _records("road construction", "software license")
    result = provider.rerank("construction", records)
    assert all("rerank_score" in r for r in result)


def test_rerank_orders_by_score_descending(provider, mock_model):
    mock_model.predict.return_value = np.array([0.2, 0.8, 0.5])
    records = _records("low", "high", "mid")
    result = provider.rerank("query", records)
    scores = [r["rerank_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_rerank_respects_limit(provider, mock_model):
    mock_model.predict.return_value = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
    records = _records("a", "b", "c", "d", "e")
    result = provider.rerank("query", records, limit=3)
    assert len(result) == 3


def test_rerank_empty_input_returns_empty(provider):
    result = provider.rerank("query", [])
    assert result == []


def test_rerank_score_is_rounded_to_4_places(provider, mock_model):
    mock_model.predict.return_value = np.array([0.123456789])
    result = provider.rerank("query", _records("title"))
    assert result[0]["rerank_score"] == round(0.123456789, 4)


def test_rerank_uses_correct_text_field(provider, mock_model):
    mock_model.predict.return_value = np.array([0.5])
    records = [{"pk": "T001_en", "title": "original", "description": "other field"}]
    provider.rerank("query", records, text_field="description")
    pairs = mock_model.predict.call_args[0][0]
    assert pairs[0][1] == "other field"


def test_rerank_missing_text_field_uses_empty_string(provider, mock_model):
    mock_model.predict.return_value = np.array([0.5])
    records = [{"pk": "T001_en"}]
    provider.rerank("query", records)
    pairs = mock_model.predict.call_args[0][0]
    assert pairs[0][1] == ""


def test_rerank_passes_query_in_each_pair(provider, mock_model):
    mock_model.predict.return_value = np.array([0.5, 0.4])
    records = _records("title one", "title two")
    provider.rerank("my query", records)
    pairs = mock_model.predict.call_args[0][0]
    assert all(p[0] == "my query" for p in pairs)


def test_model_loaded_lazily():
    p = BGERerankerProvider(model_name="fake-reranker")
    assert p._model is None


def test_model_loaded_on_first_rerank():
    p = BGERerankerProvider(model_name="fake-reranker")
    fake = MagicMock()
    fake.predict.return_value = np.array([0.5])
    with patch("sentence_transformers.CrossEncoder", return_value=fake):
        p.rerank("q", _records("title"))
    assert p._model is fake
