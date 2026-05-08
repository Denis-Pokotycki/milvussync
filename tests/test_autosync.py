"""Tests for autosync._sync_pass — uses lightweight fakes, no live services."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from sync.autosync import _sync_pass, _build_record, _load_state, _save_state


# ── helpers ────────────────────────────────────────────────────────────────────

def _row(pk="T001_en", title="Road construction", updated_at="2024-01-01T00:00:00"):
    return {
        "pk": pk,
        "tender_id": pk.split("_")[0],
        "platform_id": f"PLT-{pk}",
        "tender_national_id": f"NAT-{pk}",
        "publication_date": "2024-01-01",
        "closing_date": "2024-06-01",
        "estimated_total_value": 500000.0,
        "language_code": pk.split("_")[1] if "_" in pk else "en",
        "title": title,
        "nut_code": "DE600",
        "nut_label": "Hamburg",
        "cpv_codes": ["45233000-9"],
        "updated_at": updated_at,
    }


def _make_repo(rows):
    repo = MagicMock()
    repo.count.return_value = len(rows)
    repo.fetch_page.return_value = rows
    return repo


def _make_embedder(vec=None):
    embedder = MagicMock()
    embedder.embed.return_value = vec or [0.1] * 1024
    return embedder


def _make_milvus():
    return MagicMock()


def _make_meili():
    return MagicMock()


# ── _build_record ─────────────────────────────────────────────────────────────

def test_build_record_maps_all_fields():
    row = _row()
    embedding = [0.5] * 1024
    record = _build_record(row, embedding)
    assert record["pk"] == "T001_en"
    assert record["title"] == "Road construction"
    assert record["title_embedding"] == embedding
    assert record["cpv_codes"] == ["45233000-9"]


def test_build_record_truncates_title():
    row = _row(title="x" * 70_000)
    record = _build_record(row, [0.0] * 1024)
    assert len(record["title"]) == 65_535


def test_build_record_empty_cpv_defaults_to_list():
    row = _row()
    row["cpv_codes"] = None
    record = _build_record(row, [0.0] * 1024)
    assert record["cpv_codes"] == []


# ── _sync_pass — happy path ───────────────────────────────────────────────────

def test_sync_pass_upserts_rows_to_milvus(tmp_path):
    rows = [_row("T001_en", "Bridge repair"), _row("T002_en", "Water plant")]
    repo = _make_repo(rows)
    embedder = _make_embedder()
    milvus = _make_milvus()
    count = _sync_pass(repo, embedder, milvus, str(tmp_path / "state.json"))
    assert count == 2
    assert milvus.upsert.call_count == 2


def test_sync_pass_also_batches_to_meilisearch(tmp_path):
    rows = [_row("T001_en", "Bridge repair")]
    repo = _make_repo(rows)
    meili = _make_meili()
    _sync_pass(_make_repo(rows), _make_embedder(), _make_milvus(),
               str(tmp_path / "state.json"), meili=meili)
    meili.upsert_documents.assert_called_once()
    docs = meili.upsert_documents.call_args[0][0]
    assert "title_embedding" not in docs[0]


def test_sync_pass_saves_cursor_after_success(tmp_path):
    state_path = str(tmp_path / "state.json")
    rows = [_row(updated_at="2024-06-15T12:00:00")]
    _sync_pass(_make_repo(rows), _make_embedder(), _make_milvus(), state_path)
    state = _load_state(state_path)
    assert state["last_synced_at"] == "2024-06-15T12:00:00"


def test_sync_pass_returns_zero_when_no_rows(tmp_path):
    repo = MagicMock()
    repo.count.return_value = 0
    count = _sync_pass(repo, _make_embedder(), _make_milvus(),
                       str(tmp_path / "state.json"))
    assert count == 0


# ── _sync_pass — error handling ───────────────────────────────────────────────

def test_sync_pass_skips_row_with_empty_title(tmp_path):
    rows = [_row(title=""), _row("T002_en", "Valid title")]
    count = _sync_pass(_make_repo(rows), _make_embedder(), _make_milvus(),
                       str(tmp_path / "state.json"))
    assert count == 1


def test_sync_pass_skips_row_with_whitespace_title(tmp_path):
    rows = [_row(title="   "), _row("T002_en", "Valid title")]
    count = _sync_pass(_make_repo(rows), _make_embedder(), _make_milvus(),
                       str(tmp_path / "state.json"))
    assert count == 1


def test_sync_pass_continues_after_embed_error(tmp_path):
    embedder = MagicMock()
    embedder.embed.side_effect = [Exception("model error"), [0.1] * 1024]
    rows = [_row("T001_en", "First"), _row("T002_en", "Second")]
    milvus = _make_milvus()
    count = _sync_pass(_make_repo(rows), embedder, milvus, str(tmp_path / "state.json"))
    assert count == 1


def test_sync_pass_continues_after_milvus_error(tmp_path):
    milvus = MagicMock()
    milvus.upsert.side_effect = [Exception("milvus down"), None]
    rows = [_row("T001_en", "First"), _row("T002_en", "Second")]
    count = _sync_pass(_make_repo(rows), _make_embedder(), milvus,
                       str(tmp_path / "state.json"))
    assert count == 1


def test_sync_pass_meili_error_does_not_abort_sync(tmp_path):
    meili = MagicMock()
    meili.upsert_documents.side_effect = Exception("meili down")
    rows = [_row()]
    count = _sync_pass(_make_repo(rows), _make_embedder(), _make_milvus(),
                       str(tmp_path / "state.json"), meili=meili)
    assert count == 1


def test_sync_pass_cursor_uses_since_from_state(tmp_path):
    state_path = str(tmp_path / "state.json")
    _save_state(state_path, {"last_synced_at": "2024-01-01T00:00:00"})
    repo = _make_repo([])
    _sync_pass(repo, _make_embedder(), _make_milvus(), state_path)
    repo.count.assert_called_with(since="2024-01-01T00:00:00")


def test_sync_pass_handles_datetime_updated_at(tmp_path):
    row = _row()
    row["updated_at"] = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    state_path = str(tmp_path / "state.json")
    _sync_pass(_make_repo([row]), _make_embedder(), _make_milvus(), state_path)
    state = _load_state(state_path)
    assert "2024-06-15" in state["last_synced_at"]
