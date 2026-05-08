import json
import time
import pulsar
from django.conf import settings
from .base_consumer import BasePulsarConsumer
from sync.tc_milvus.client import TenderMilvusClient
from sync.embeddings.openai_provider import OpenAIEmbeddingProvider

TOPIC_ATTACHMENTS = "attachments"


class MilvusSyncConsumer(BasePulsarConsumer):
    """
    Consumes from the Pulsar `attachments` topic and upserts tender title
    embeddings into Milvus. One subscription per running instance; a separate
    backfill subscription can be created via the backfill_milvus management command.
    """

    def __init__(self, consume_topic: str = TOPIC_ATTACHMENTS, **kwargs):
        consumer_options = kwargs.pop("consumer_options", {})
        # Start from the beginning of the topic log unless overridden
        consumer_options.setdefault(
            "initial_position", pulsar.InitialPosition.Earliest
        )
        consumer_options.setdefault(
            "unacked_messages_timeout_ms",
            settings.MILVUS_SYNC_UNACKED_TIMEOUT_MS,
        )
        kwargs["consumer_options"] = consumer_options

        # No Pulsar schema — attachments topic carries raw JSON bytes
        super().__init__(consume_topic=consume_topic, schema=None, **kwargs)

        self.milvus = TenderMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.MILVUS_COLLECTION,
            vector_dim=settings.MILVUS_VECTOR_DIM,
        )
        self.embedder = OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_EMBEDDING_MODEL,
        )

    def before_run(self) -> None:
        self.milvus.ensure_collection()

    def process_message(self, message) -> None:
        # --- Permanent errors: bad payload → log + return (base consumer ACKs) ---
        try:
            payload = json.loads(message.data())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.logger.warning("milvus_sync.skip.bad_json", error=str(exc))
            return

        platform_id = payload.get("platform_id")
        if not platform_id:
            self.logger.warning(
                "milvus_sync.skip.missing_platform_id", keys=list(payload)
            )
            return

        other_raw = payload.get("other", "{}")
        try:
            other = (
                json.loads(other_raw)
                if isinstance(other_raw, str)
                else (other_raw or {})
            )
        except (json.JSONDecodeError, TypeError):
            other = {}

        title = (other.get("title") or "").strip()

        # --- Transient errors: external calls → raise → base consumer NACKs ---
        embedding = self.embedder.embed(title)

        record = {
            "platform_id":      platform_id,
            "title":            title[:65_535],
            "title_embedding":  embedding,
            "country_id":       str(other.get("country_id") or "")[:16],
            "cpv":              str(other.get("cpv") or "")[:64],
            "procedure_type":   str(other.get("procedure_type") or "")[:128],
            "publication_date": str(other.get("publication_date") or "")[:32],
            "closing_date":     str(other.get("closing_date") or "")[:32],
            "synced_at":        int(time.time()),
        }

        self.milvus.upsert(record)

        self.logger.info(
            "milvus_sync.upserted",
            platform_id=platform_id,
            title_len=len(title),
        )
