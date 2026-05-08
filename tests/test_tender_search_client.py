"""Tests for TenderSearchMilvusClient — mocks pymilvus.MilvusClient."""
import pytest
from unittest.mock import MagicMock, patch, call
from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient


@pytest.fixture
def mock_milvus():
    return MagicMock()


@pytest.fixture
def client(mock_milvus):
    c = TenderSearchMilvusClient(uri="http://localhost:19530", collection_name="tender_search")
    c._client = mock_milvus
    return c


def _hit(pk="T001_en", title="Road repair", score=0.95):
    entity = MagicMock()
    entity.get.side_effect = lambda key, default=None: {
        "pk": pk, "tender_id": "T001", "language_code": "en",
        "title": title, "nut_code": "DE600", "nut_label": "Hamburg",
        "cpv_codes": ["45233000-9"], "publication_date": "2024-01-01",
        "closing_date": "2024-06-01", "estimated_total_value": 500000.0,
    }.get(key, default)
    hit = MagicMock()
    hit.entity = entity
    hit.score = score
    return hit


# ── ensure_collection ────────────────────────────────────────────────────────

def test_ensure_collection_skips_when_exists(client, mock_milvus):
    mock_milvus.has_collection.return_value = True
    client.ensure_collection()
    mock_milvus.create_collection.assert_not_called()


def test_ensure_collection_creates_when_missing(client, mock_milvus):
    mock_milvus.has_collection.return_value = False
    mock_milvus.create_schema.return_value = MagicMock()
    mock_milvus.prepare_index_params.return_value = MagicMock()
    client.ensure_collection()
    mock_milvus.create_collection.assert_called_once()


# ── upsert ────────────────────────────────────────────────────────────────────

def test_upsert_calls_milvus_upsert(client, mock_milvus):
    record = {"pk": "T001_en", "title": "Bridge construction", "title_embedding": [0.1] * 1024}
    client.upsert(record)
    mock_milvus.upsert.assert_called_once_with(
        collection_name="tender_search", data=[record]
    )


def test_upsert_retries_on_exception(client, mock_milvus):
    mock_milvus.upsert.side_effect = [Exception("timeout"), Exception("timeout"), None]
    record = {"pk": "T001_en", "title": "test", "title_embedding": [0.0] * 1024}
    client.upsert(record)
    assert mock_milvus.upsert.call_count == 3


def test_upsert_raises_after_max_retries(client, mock_milvus):
    mock_milvus.upsert.side_effect = Exception("always fails")
    with pytest.raises(Exception):
        client.upsert({"pk": "T001_en", "title": "test", "title_embedding": [0.0] * 1024})


# ── search ────────────────────────────────────────────────────────────────────

def test_search_returns_list_of_dicts(client, mock_milvus):
    mock_milvus.search.return_value = [[_hit()]]
    result = client.search([0.1] * 1024, limit=5)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["pk"] == "T001_en"
    assert result[0]["score"] == 0.95


def test_search_returns_empty_on_no_hits(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    result = client.search([0.0] * 1024)
    assert result == []


def test_search_with_language_filter(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    client.search([0.0] * 1024, language_code="de")
    call_kwargs = mock_milvus.search.call_args[1]
    assert 'language_code == "de"' in call_kwargs["filter"]


def test_search_with_cpv_filter(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    client.search([0.0] * 1024, cpv_code="45233000-9")
    call_kwargs = mock_milvus.search.call_args[1]
    assert "array_contains" in call_kwargs["filter"]


def test_search_with_date_filter(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    client.search([0.0] * 1024, publication_date_gte="2024-01-01")
    call_kwargs = mock_milvus.search.call_args[1]
    assert "publication_date" in call_kwargs["filter"]


def test_search_no_filter_passes_empty_string(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    client.search([0.0] * 1024)
    call_kwargs = mock_milvus.search.call_args[1]
    assert call_kwargs["filter"] == ""


def test_search_multiple_filters_joined_with_and(client, mock_milvus):
    mock_milvus.search.return_value = [[]]
    client.search([0.0] * 1024, language_code="en", cpv_code="45000000-7")
    call_kwargs = mock_milvus.search.call_args[1]
    assert " && " in call_kwargs["filter"]


# ── healthcheck ───────────────────────────────────────────────────────────────

def test_healthcheck_returns_true(client, mock_milvus):
    mock_milvus.list_collections.return_value = []
    assert client.healthcheck() is True


def test_healthcheck_returns_false_on_exception(client, mock_milvus):
    mock_milvus.list_collections.side_effect = Exception("unreachable")
    assert client.healthcheck() is False


# ── drop_collection ───────────────────────────────────────────────────────────

def test_drop_collection_when_exists(client, mock_milvus):
    mock_milvus.has_collection.return_value = True
    client.drop_collection()
    mock_milvus.drop_collection.assert_called_once_with("tender_search")


def test_drop_collection_skips_when_not_exists(client, mock_milvus):
    mock_milvus.has_collection.return_value = False
    client.drop_collection()
    mock_milvus.drop_collection.assert_not_called()


# ── count ─────────────────────────────────────────────────────────────────────

def test_count_returns_count_value(client, mock_milvus):
    mock_milvus.query.return_value = [{"count(*)": 42}]
    assert client.count() == 42


def test_count_returns_zero_on_empty_result(client, mock_milvus):
    mock_milvus.query.return_value = []
    assert client.count() == 0


def test_count_returns_zero_on_exception(client, mock_milvus):
    mock_milvus.query.side_effect = Exception("query failed")
    assert client.count() == 0


# ── list_records ──────────────────────────────────────────────────────────────

def test_list_records_returns_rows(client, mock_milvus):
    rows = [{"pk": "T001_en", "title": "Road repair"}]
    mock_milvus.query.return_value = rows
    assert client.list_records() == rows


def test_list_records_returns_empty_on_exception(client, mock_milvus):
    mock_milvus.query.side_effect = Exception("query failed")
    assert client.list_records() == []


def test_list_records_returns_empty_when_none(client, mock_milvus):
    mock_milvus.query.return_value = None
    assert client.list_records() == []
