"""
Unit tests for the TenderSearchConsumer payload mapping logic:
pk construction, field extraction, empty-title skip, CPV codes.

These tests call process_message() directly without starting the consumer,
so no Pulsar connection is made and fake_pulsar is not required.
"""
import json
import pytest
from tests.fakes.pulsar import FakeMessage


def _make_message(payload: dict) -> FakeMessage:
    return FakeMessage(json.dumps(payload).encode("utf-8"))


def _make_consumer(fake_tender_search_milvus, fake_bge):
    from sync.tc_pulsar.consumers.tender_search_consumer import TenderSearchConsumer
    return TenderSearchConsumer(subscription_name="test_sub")


def _client(fake_tender_search_milvus):
    """Return the FakeTenderSearchClient that was created during consumer init."""
    return fake_tender_search_milvus.last_search_client


# ── pk construction ──────────────────────────────────────────────────────────

def test_pk_is_tender_id_underscore_language_code(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T001_en",
        "tender_id": "T001",
        "language_code": "en",
        "title": "Road construction works",
        "platform_id": "PLT001",
        "tender_national_id": "CIG-001",
        "publication_date": "2024-01-15",
        "closing_date": "2024-03-31",
        "estimated_total_value": 500000.0,
        "nut_code": "ITC1",
        "nut_label": "Piemonte",
        "cpv_codes": ["45233120-6"],
    }))

    rec = _client(fake_tender_search_milvus).get_record("T001_en")
    assert rec is not None
    assert rec["pk"] == "T001_en"
    assert rec["tender_id"] == "T001"
    assert rec["language_code"] == "en"


def test_multiple_languages_produce_separate_records(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    for lang in ("en", "it", "fr"):
        consumer.process_message(_make_message({
            "pk": f"T001_{lang}",
            "tender_id": "T001",
            "language_code": lang,
            "title": f"Title in {lang}",
            "platform_id": "PLT001",
            "tender_national_id": "CIG-001",
            "publication_date": "2024-01-15",
            "closing_date": "2024-03-31",
            "estimated_total_value": 100000.0,
            "nut_code": "ITC1",
            "nut_label": "Piemonte",
            "cpv_codes": [],
        }))

    client = _client(fake_tender_search_milvus)
    assert client.record_count() == 3
    for lang in ("en", "it", "fr"):
        assert client.get_record(f"T001_{lang}") is not None


# ── field extraction ─────────────────────────────────────────────────────────

def test_all_fields_mapped_correctly(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T002_fr",
        "tender_id": "T002",
        "language_code": "fr",
        "title": "Fourniture de matériel informatique",
        "platform_id": "PLT002",
        "tender_national_id": "CIG-002",
        "publication_date": "2024-02-01",
        "closing_date": "2024-04-15",
        "estimated_total_value": 250000.0,
        "nut_code": "FR101",
        "nut_label": "Paris",
        "cpv_codes": ["30213000-5", "48000000-8"],
    }))

    rec = _client(fake_tender_search_milvus).get_record("T002_fr")
    assert rec["platform_id"] == "PLT002"
    assert rec["tender_national_id"] == "CIG-002"
    assert rec["publication_date"] == "2024-02-01"
    assert rec["closing_date"] == "2024-04-15"
    assert rec["estimated_total_value"] == 250000.0
    assert rec["nut_code"] == "FR101"
    assert rec["nut_label"] == "Paris"
    assert rec["cpv_codes"] == ["30213000-5", "48000000-8"]


def test_cpv_codes_stored_as_list(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T003_en",
        "tender_id": "T003",
        "language_code": "en",
        "title": "Medical diagnostic equipment",
        "platform_id": "PLT003",
        "tender_national_id": "CIG-003",
        "publication_date": "2024-03-01",
        "closing_date": "2024-05-30",
        "estimated_total_value": 1200000.0,
        "nut_code": "UKI3",
        "nut_label": "Inner London",
        "cpv_codes": ["33111000-1", "50400000-9"],
    }))
    rec = _client(fake_tender_search_milvus).get_record("T003_en")
    assert isinstance(rec["cpv_codes"], list)
    assert "33111000-1" in rec["cpv_codes"]


def test_missing_cpv_codes_defaults_to_empty_list(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T004_es",
        "tender_id": "T004",
        "language_code": "es",
        "title": "Servicios de consultoría digital",
        "platform_id": "PLT004",
        "tender_national_id": "CIG-004",
        "publication_date": "2024-04-01",
        "closing_date": "2024-06-30",
        "estimated_total_value": 750000.0,
        "nut_code": "ES300",
        "nut_label": "Madrid",
    }))
    rec = _client(fake_tender_search_milvus).get_record("T004_es")
    assert rec["cpv_codes"] == []


# ── empty-title skip ─────────────────────────────────────────────────────────

def test_empty_title_is_skipped(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T005_en",
        "tender_id": "T005",
        "language_code": "en",
        "title": "",
        "platform_id": "PLT005",
        "tender_national_id": "CIG-005",
        "publication_date": "2024-05-01",
        "closing_date": "2024-07-31",
        "estimated_total_value": 380000.0,
        "nut_code": "DEA2",
        "nut_label": "Köln",
        "cpv_codes": [],
    }))
    assert _client(fake_tender_search_milvus).record_count() == 0


def test_whitespace_only_title_is_skipped(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "pk": "T006_de",
        "tender_id": "T006",
        "language_code": "de",
        "title": "   \t  ",
        "platform_id": "PLT006",
        "tender_national_id": "CIG-006",
        "publication_date": "2024-06-01",
        "closing_date": "2024-08-31",
        "estimated_total_value": 0.0,
        "nut_code": "",
        "nut_label": "",
        "cpv_codes": [],
    }))
    assert _client(fake_tender_search_milvus).record_count() == 0


def test_missing_pk_is_skipped(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(_make_message({
        "tender_id": "T007",
        "language_code": "en",
        "title": "Some valid title",
    }))
    assert _client(fake_tender_search_milvus).record_count() == 0


def test_bad_json_is_handled(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    consumer.process_message(FakeMessage(b"not-json-at-all{{{"))
    assert _client(fake_tender_search_milvus).record_count() == 0


# ── idempotency ──────────────────────────────────────────────────────────────

def test_upsert_is_idempotent(fake_tender_search_milvus, fake_bge):
    consumer = _make_consumer(fake_tender_search_milvus, fake_bge)
    payload = {
        "pk": "T001_en",
        "tender_id": "T001",
        "language_code": "en",
        "title": "Road construction works",
        "platform_id": "PLT001",
        "tender_national_id": "CIG-001",
        "publication_date": "2024-01-15",
        "closing_date": "2024-03-31",
        "estimated_total_value": 500000.0,
        "nut_code": "ITC1",
        "nut_label": "Piemonte",
        "cpv_codes": ["45233120-6"],
    }
    consumer.process_message(_make_message(payload))
    consumer.process_message(_make_message(payload))
    assert _client(fake_tender_search_milvus).record_count() == 1
