"""Tests for BGEEmbeddingProvider — mocks SentenceTransformer so no model download."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from sync.embeddings.bge_provider import BGEEmbeddingProvider


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.encode.side_effect = lambda text, normalize_embeddings=True: np.array([0.1] * 1024)
    return model


@pytest.fixture
def provider(mock_model):
    p = BGEEmbeddingProvider(model_name="fake-model")
    p._model = mock_model
    return p


def test_embed_returns_list_of_floats(provider):
    result = provider.embed("road construction")
    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(v, float) for v in result)


def test_embed_empty_string_does_not_raise(provider):
    result = provider.embed("")
    assert len(result) == 1024


def test_embed_passes_text_without_prefix(provider, mock_model):
    provider.embed("bridge repair")
    mock_model.encode.assert_called_once_with("bridge repair", normalize_embeddings=True)


def test_embed_query_prepends_instruction(provider, mock_model):
    provider.embed_query("solar energy")
    call_text = mock_model.encode.call_args[0][0]
    assert call_text.startswith("Represent this sentence for searching relevant passages: ")
    assert "solar energy" in call_text


def test_embed_query_empty_string_uses_instruction_only(provider, mock_model):
    provider.embed_query("")
    call_text = mock_model.encode.call_args[0][0]
    assert call_text == "Represent this sentence for searching relevant passages: "


def test_embed_query_returns_list_of_floats(provider):
    result = provider.embed_query("water treatment")
    assert isinstance(result, list)
    assert len(result) == 1024


def test_dim_is_1024(provider):
    assert provider.dim == 1024


def test_model_loaded_lazily():
    p = BGEEmbeddingProvider(model_name="fake-model")
    assert p._model is None


def test_model_loaded_on_first_embed():
    p = BGEEmbeddingProvider(model_name="fake-model")
    fake = MagicMock()
    fake.encode.return_value = np.array([0.0] * 1024)
    with patch("sentence_transformers.SentenceTransformer", return_value=fake):
        p.embed("test")
    assert p._model is fake


def test_model_not_reloaded_on_second_call(provider, mock_model):
    provider.embed("first")
    provider.embed("second")
    assert mock_model.encode.call_count == 2
