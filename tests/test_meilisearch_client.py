"""Tests for TenderSearchMeilisearchClient — mocks meilisearch.Client."""
import pytest
from unittest.mock import MagicMock, patch
import meilisearch.errors
from sync.tc_meilisearch.client import TenderSearchMeilisearchClient


@pytest.fixture
def mock_meili_client():
    return MagicMock()


@pytest.fixture
def client(mock_meili_client):
    c = TenderSearchMeilisearchClient(url="http://localhost:7700", api_key="test-key")
    c._client = mock_meili_client
    return c


# ── ensure_index ──────────────────────────────────────────────────────────────

def test_ensure_index_skips_create_when_exists(client, mock_meili_client):
    mock_meili_client.get_index.return_value = MagicMock()
    mock_index = MagicMock()
    mock_index.update_settings.return_value = MagicMock(task_uid=1)
    mock_meili_client.index.return_value = mock_index
    mock_meili_client.wait_for_task.return_value = None
    client.ensure_index()
    mock_meili_client.create_index.assert_not_called()


def test_ensure_index_creates_when_missing(client, mock_meili_client):
    api_error = meilisearch.errors.MeilisearchApiError("not found", MagicMock(status_code=404, text=""))
    api_error.status_code = 404
    mock_meili_client.get_index.side_effect = api_error
    mock_meili_client.create_index.return_value = MagicMock(task_uid=1)
    mock_index = MagicMock()
    mock_index.update_settings.return_value = MagicMock(task_uid=2)
    mock_meili_client.index.return_value = mock_index
    client.ensure_index()
    mock_meili_client.create_index.assert_called_once()


def test_ensure_index_reraises_non_404_error(client, mock_meili_client):
    api_error = meilisearch.errors.MeilisearchApiError("server error", MagicMock(status_code=500, text=""))
    api_error.status_code = 500
    mock_meili_client.get_index.side_effect = api_error
    with pytest.raises(meilisearch.errors.MeilisearchApiError):
        client.ensure_index()


# ── upsert_documents ──────────────────────────────────────────────────────────

def test_upsert_documents_calls_update_documents(client, mock_meili_client):
    mock_index = MagicMock()
    mock_index.update_documents.return_value = MagicMock(task_uid=1)
    mock_meili_client.index.return_value = mock_index
    docs = [{"pk": "T001_en", "title": "Road repair"}]
    client.upsert_documents(docs)
    mock_index.update_documents.assert_called_once_with(docs, primary_key="pk")


def test_upsert_documents_skips_empty_list(client, mock_meili_client):
    mock_index = MagicMock()
    mock_meili_client.index.return_value = mock_index
    client.upsert_documents([])
    mock_index.update_documents.assert_not_called()


# ── search ────────────────────────────────────────────────────────────────────

def test_search_returns_hits_with_meili_score(client, mock_meili_client):
    mock_index = MagicMock()
    mock_index.search.return_value = {
        "hits": [
            {"pk": "T001_en", "title": "Road repair", "_rankingScore": 0.987654},
        ]
    }
    mock_meili_client.index.return_value = mock_index
    result = client.search("road", limit=5)
    assert len(result) == 1
    assert result[0]["meili_score"] == 0.9877
    assert "_rankingScore" not in result[0]


def test_search_strips_underscore_fields(client, mock_meili_client):
    mock_index = MagicMock()
    mock_index.search.return_value = {
        "hits": [{"pk": "T001_en", "_rankingScore": 0.9, "_formatted": {}}]
    }
    mock_meili_client.index.return_value = mock_index
    result = client.search("query")
    assert "_formatted" not in result[0]
    assert "_rankingScore" not in result[0]


def test_search_returns_empty_on_no_hits(client, mock_meili_client):
    mock_index = MagicMock()
    mock_index.search.return_value = {"hits": []}
    mock_meili_client.index.return_value = mock_index
    assert client.search("nothing") == []


def test_search_missing_ranking_score_defaults_to_zero(client, mock_meili_client):
    mock_index = MagicMock()
    mock_index.search.return_value = {"hits": [{"pk": "T001_en", "title": "test"}]}
    mock_meili_client.index.return_value = mock_index
    result = client.search("test")
    assert result[0]["meili_score"] == 0.0


# ── healthcheck ───────────────────────────────────────────────────────────────

def test_healthcheck_returns_true(client, mock_meili_client):
    mock_meili_client.is_healthy.return_value = True
    assert client.healthcheck() is True


def test_healthcheck_returns_false_on_exception(client, mock_meili_client):
    mock_meili_client.is_healthy.side_effect = Exception("unreachable")
    assert client.healthcheck() is False
