import json
import pytest

from sync.tc_pulsar.consumers.milvus_sync_consumer import MilvusSyncConsumer


pytestmark = pytest.mark.django_db

TOPIC_ATTACHMENTS = "attachments"
TEST_TOPIC = "test_attachments"


def _make_payload(platform_id="plat1", title="Road works contract",
                  country_id="IT", cpv="45233120-6", procedure_type="Open",
                  publication_date="2024-01-01", closing_date="2024-03-01",
                  other_override=None):
    other = other_override if other_override is not None else {
        "title": title,
        "country_id": country_id,
        "cpv": cpv,
        "procedure_type": procedure_type,
        "publication_date": publication_date,
        "closing_date": closing_date,
    }
    return {
        "platform_id": platform_id,
        "urls": ["http://example.com/a.pdf"],
        "other": json.dumps(other),
    }


def _send(fake_pulsar, consumer, payload_dict):
    topic = consumer.build_topic_name(TOPIC_ATTACHMENTS)
    fake_pulsar.broker.send(topic, json.dumps(payload_dict).encode())


def _make_consumer(fake_pulsar, settings, topic=TOPIC_ATTACHMENTS):
    settings.PULSAR_NAMESPACE = "testns"
    settings.PULSAR_TENANT = "public"
    consumer = MilvusSyncConsumer(
        consume_topic=topic,
        consumer_options={"initial_position": 0},
    )
    consumer.connect()
    return consumer


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_message_upserted(fake_pulsar, fake_milvus, fake_embedder, settings):
    consumer = _make_consumer(fake_pulsar, settings)
    _send(fake_pulsar, consumer, _make_payload())

    consumer.consume()

    assert fake_milvus.last_client is not None
    record = fake_milvus.last_client.get_record("plat1")
    assert record is not None
    assert record["platform_id"] == "plat1"
    assert record["title"] == "Road works contract"
    assert record["country_id"] == "IT"
    assert record["cpv"] == "45233120-6"
    assert record["title_embedding"] == [0.1, 0.2, 0.3]
    assert isinstance(record["synced_at"], int)
    # Message ACKed — nothing left in pending
    assert consumer.consumer._pending == {}

    consumer.disconnect()


def test_idempotent_upsert(fake_pulsar, fake_milvus, fake_embedder, settings):
    consumer = _make_consumer(fake_pulsar, settings)
    payload = _make_payload()
    _send(fake_pulsar, consumer, payload)
    _send(fake_pulsar, consumer, payload)

    consumer.consume()
    consumer.consume()

    assert fake_milvus.last_client.record_count() == 1
    consumer.disconnect()


# ---------------------------------------------------------------------------
# Permanent errors (bad payload) → ACK, no Milvus write
# ---------------------------------------------------------------------------

def test_missing_platform_id_is_acked(fake_pulsar, fake_milvus, fake_embedder, settings):
    consumer = _make_consumer(fake_pulsar, settings)
    payload = {"urls": [], "other": json.dumps({"title": "No ID"})}
    _send(fake_pulsar, consumer, json.dumps(payload).encode() if False else payload)

    consumer.consume()

    assert fake_milvus.last_client is None or fake_milvus.last_client.record_count() == 0
    assert consumer.consumer._pending == {}
    consumer.disconnect()


def test_bad_json_is_acked(fake_pulsar, fake_milvus, fake_embedder, settings):
    consumer = _make_consumer(fake_pulsar, settings)
    topic = consumer.build_topic_name(TOPIC_ATTACHMENTS)
    # Push raw non-JSON bytes directly
    from tests.fakes.pulsar import FakeMessage
    fake_pulsar.broker.get_topic(topic).push(FakeMessage(b"not-json-at-all"))

    consumer.consume()

    assert fake_milvus.last_client is None or fake_milvus.last_client.record_count() == 0
    assert consumer.consumer._pending == {}
    consumer.disconnect()


# ---------------------------------------------------------------------------
# Transient errors → NACK
# ---------------------------------------------------------------------------

def test_openai_error_causes_nack(fake_pulsar, fake_milvus, settings, monkeypatch):
    import openai
    from sync.embeddings.openai_provider import OpenAIEmbeddingProvider

    monkeypatch.setattr(
        OpenAIEmbeddingProvider,
        "embed",
        lambda self, text: (_ for _ in ()).throw(
            openai.error.RateLimitError("rate limit")
        ),
    )

    consumer = _make_consumer(fake_pulsar, settings)
    _send(fake_pulsar, consumer, _make_payload(platform_id="plat-err"))

    consumer.consume()

    # Message was requeued with redelivery_count=1
    topic = consumer.build_topic_name(TOPIC_ATTACHMENTS)
    redelivered = fake_pulsar.broker.get_topic(topic).pop()
    assert redelivered is not None
    assert redelivered.redelivery_count() == 1
    assert consumer.consumer._pending == {}
    consumer.disconnect()


def test_milvus_error_causes_nack(fake_pulsar, fake_milvus, fake_embedder, settings, monkeypatch):
    monkeypatch.setattr(
        fake_milvus.FakeMilvusClient if hasattr(fake_milvus, "FakeMilvusClient") else type(fake_milvus.last_client or object()),
        "upsert",
        lambda self, record: (_ for _ in ()).throw(RuntimeError("Milvus unavailable")),
    )
    # Reset and re-patch via module attribute
    from tests.fakes import milvus as fake_mod

    class _FailUpsert(fake_mod.FakeMilvusClient):
        def upsert(self, record):
            raise RuntimeError("Milvus unavailable")

    import sync.tc_milvus.client as client_mod
    monkeypatch.setattr(client_mod, "TenderMilvusClient", _FailUpsert)

    consumer = _make_consumer(fake_pulsar, settings)
    _send(fake_pulsar, consumer, _make_payload(platform_id="plat-milvus-err"))

    consumer.consume()

    topic = consumer.build_topic_name(TOPIC_ATTACHMENTS)
    redelivered = fake_pulsar.broker.get_topic(topic).pop()
    assert redelivered is not None
    assert redelivered.redelivery_count() == 1
    consumer.disconnect()


# ---------------------------------------------------------------------------
# `other` field handling
# ---------------------------------------------------------------------------

def test_other_as_json_string(fake_pulsar, fake_milvus, fake_embedder, settings):
    """other arrives as a JSON-encoded string (standard Attachment schema)."""
    consumer = _make_consumer(fake_pulsar, settings)
    _send(fake_pulsar, consumer, _make_payload(
        platform_id="plat2", country_id="DE", cpv="72000000-5"
    ))

    consumer.consume()

    record = fake_milvus.last_client.get_record("plat2")
    assert record["country_id"] == "DE"
    assert record["cpv"] == "72000000-5"
    consumer.disconnect()


def test_other_field_missing(fake_pulsar, fake_milvus, fake_embedder, settings):
    """Payload without 'other' key should not crash; title defaults to empty string."""
    consumer = _make_consumer(fake_pulsar, settings)
    payload = {"platform_id": "plat3", "urls": []}
    _send(fake_pulsar, consumer, payload)

    consumer.consume()

    record = fake_milvus.last_client.get_record("plat3")
    assert record is not None
    assert record["title"] == ""
    consumer.disconnect()


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

def test_dead_letter_topic_name(settings):
    settings.PULSAR_NAMESPACE = "testns"
    settings.PULSAR_TENANT = "public"
    consumer = MilvusSyncConsumer(consume_topic=TOPIC_ATTACHMENTS)
    dlq = consumer._consumer_options["dead_letter_policy"].dead_letter_topic
    assert dlq == f"public/testns/{TOPIC_ATTACHMENTS}-DLQ"


# ---------------------------------------------------------------------------
# before_run
# ---------------------------------------------------------------------------

def test_before_run_calls_ensure_collection(fake_pulsar, fake_milvus, settings):
    consumer = _make_consumer(fake_pulsar, settings)
    consumer.before_run()
    assert fake_milvus.last_client is not None
    assert fake_milvus.last_client._collection_ensured
    consumer.disconnect()


# ---------------------------------------------------------------------------
# `other` field — invalid JSON fallback
# ---------------------------------------------------------------------------

def test_other_invalid_json_falls_back_to_empty(fake_pulsar, fake_milvus, fake_embedder, settings):
    """If `other` is a malformed JSON string, title defaults to '' and no crash."""
    consumer = _make_consumer(fake_pulsar, settings)
    payload = {"platform_id": "plat-bad-other", "other": "not-valid-json-{{{"}
    _send(fake_pulsar, consumer, payload)
    consumer.consume()
    record = fake_milvus.last_client.get_record("plat-bad-other")
    assert record is not None
    assert record["title"] == ""
    consumer.disconnect()
