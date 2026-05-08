import os
import pytest
import pulsar as real_pulsar

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "milvussync.settings")
os.environ.setdefault("PULSAR_URL", "pulsar://test")
os.environ.setdefault("PULSAR_NAMESPACE", "testns")
os.environ.setdefault("PULSAR_TENANT", "public")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("MILVUS_URI", "http://milvus.local:19530")
os.environ.setdefault("AUTO_SYNC_ENABLED", "false")


@pytest.fixture(autouse=False)
def fake_pulsar(monkeypatch):
    """Patch pulsar.Client to an in-memory fake for the duration of a test."""
    from tests.fakes import pulsar as fake

    fake.broker.reset()
    monkeypatch.setattr(real_pulsar, "Client", fake.FakeClient, raising=True)
    yield fake
    fake.broker.reset()


@pytest.fixture(autouse=False)
def fake_milvus(monkeypatch):
    """Patch TenderMilvusClient (legacy) with an in-memory fake."""
    from tests.fakes import milvus as fake_mod

    fake_mod.reset()
    import sync.tc_milvus.client as client_mod
    import sync.tc_pulsar.consumers.milvus_sync_consumer as consumer_mod

    monkeypatch.setattr(
        client_mod, "TenderMilvusClient", fake_mod.FakeMilvusClient, raising=True
    )
    monkeypatch.setattr(
        consumer_mod, "TenderMilvusClient", fake_mod.FakeMilvusClient, raising=True
    )
    yield fake_mod
    fake_mod.reset()


@pytest.fixture(autouse=False)
def fake_tender_search_milvus(monkeypatch):
    """Patch TenderSearchMilvusClient with an in-memory fake."""
    from tests.fakes import milvus as fake_mod

    fake_mod.reset_search()
    import sync.tc_milvus.tender_search_client as ts_client_mod
    import sync.tc_pulsar.consumers.tender_search_consumer as ts_consumer_mod

    monkeypatch.setattr(
        ts_client_mod,
        "TenderSearchMilvusClient",
        fake_mod.FakeTenderSearchClient,
        raising=True,
    )
    monkeypatch.setattr(
        ts_consumer_mod,
        "TenderSearchMilvusClient",
        fake_mod.FakeTenderSearchClient,
        raising=True,
    )
    yield fake_mod
    fake_mod.reset_search()


@pytest.fixture(autouse=False)
def fake_embedder(monkeypatch):
    """Return a fixed 3-element vector for any input, bypassing OpenAI calls."""
    from sync.embeddings.openai_provider import OpenAIEmbeddingProvider

    monkeypatch.setattr(
        OpenAIEmbeddingProvider, "embed", lambda self, text: [0.1, 0.2, 0.3]
    )
    yield


@pytest.fixture(autouse=False)
def fake_bge(monkeypatch):
    """Return a fixed 1024-element zero vector, bypassing sentence-transformers."""
    from sync.embeddings.bge_provider import BGEEmbeddingProvider

    dummy = [0.0] * 1024
    monkeypatch.setattr(BGEEmbeddingProvider, "embed", lambda self, text: dummy)
    monkeypatch.setattr(BGEEmbeddingProvider, "embed_query", lambda self, text: dummy)
    yield
