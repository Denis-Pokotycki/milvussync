import pytest
from unittest.mock import MagicMock, patch, call

from sync.tc_milvus.client import TenderMilvusClient
from tests.fakes.milvus import FakeMilvusClient


def _make_client(**kwargs):
    defaults = dict(
        uri="http://localhost:19530",
        token="",
        collection_name="tenders",
        vector_dim=3,
    )
    defaults.update(kwargs)
    return TenderMilvusClient(**defaults)


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_creates_when_missing(monkeypatch):
    mock_milvus = MagicMock()
    mock_milvus.has_collection.return_value = False

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        client.ensure_collection()

    mock_milvus.create_collection.assert_called_once()
    args, kwargs = mock_milvus.create_collection.call_args
    assert kwargs.get("collection_name") == "tenders"


def test_ensure_collection_skips_when_exists(monkeypatch):
    mock_milvus = MagicMock()
    mock_milvus.has_collection.return_value = True

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        client.ensure_collection()

    mock_milvus.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

def test_upsert_calls_milvus_client(monkeypatch):
    mock_milvus = MagicMock()

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        record = {
            "platform_id": "p1",
            "title": "test",
            "title_embedding": [0.1, 0.2, 0.3],
            "country_id": "IT",
            "cpv": "45000000-7",
            "procedure_type": "Open",
            "publication_date": "2024-01-01",
            "closing_date": "2024-03-01",
            "synced_at": 1700000000,
        }
        client.upsert(record)

    mock_milvus.upsert.assert_called_once_with(
        collection_name="tenders", data=[record]
    )


def test_upsert_idempotent():
    """Two upserts with the same platform_id result in one record (dict keyed by platform_id)."""
    fake = FakeMilvusClient(collection_name="tenders", vector_dim=3)
    record = {
        "platform_id": "p1",
        "title": "first",
        "title_embedding": [0.1, 0.2, 0.3],
        "country_id": "",
        "cpv": "",
        "procedure_type": "",
        "publication_date": "",
        "closing_date": "",
        "synced_at": 1,
    }
    fake.upsert(record)
    record_v2 = {**record, "title": "updated"}
    fake.upsert(record_v2)

    assert fake.record_count() == 1
    assert fake.get_record("p1")["title"] == "updated"


def test_upsert_retries_on_exception(monkeypatch):
    call_count = 0
    mock_milvus = MagicMock()

    def _flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")

    mock_milvus.upsert.side_effect = _flaky

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        client.upsert({"platform_id": "p1", "title_embedding": [0.1, 0.2, 0.3]})

    assert call_count == 3


# ---------------------------------------------------------------------------
# healthcheck
# ---------------------------------------------------------------------------

def test_healthcheck_returns_true_when_collection_exists(monkeypatch):
    mock_milvus = MagicMock()
    mock_milvus.has_collection.return_value = True

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        assert client.healthcheck() is True


def test_healthcheck_returns_false_on_exception(monkeypatch):
    mock_milvus = MagicMock()
    mock_milvus.has_collection.side_effect = RuntimeError("unreachable")

    with patch("sync.tc_milvus.client.MilvusClient", return_value=mock_milvus):
        client = _make_client()
        assert client.healthcheck() is False
