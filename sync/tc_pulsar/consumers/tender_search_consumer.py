import json
from django.conf import settings
from .base_consumer import BasePulsarConsumer
from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient
from sync.embeddings.bge_provider import BGEEmbeddingProvider

TOPIC = "tender-title-sync"


class TenderSearchConsumer(BasePulsarConsumer):
    """
    Reads tender-title-sync Pulsar messages, generates BGE title embeddings,
    and upserts into the tender_search Milvus collection.

    Error handling:
      bad JSON / missing pk / empty title  → return  → base ACKs  (permanent skip)
      embedder.embed() raises              → propagates → base NACKs (transient)
      milvus.upsert() raises              → propagates → base NACKs (transient)
    """

    def __init__(self, **kwargs):
        super().__init__(consume_topic=TOPIC, schema=None, **kwargs)

        self.milvus = TenderSearchMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.TENDER_SEARCH_COLLECTION,
            vector_dim=settings.TENDER_SEARCH_VECTOR_DIM,
        )
        self.embedder = BGEEmbeddingProvider(settings.EMBEDDING_MODEL_NAME)

    def before_run(self) -> None:
        self.milvus.ensure_collection()

    def process_message(self, message) -> None:
        # --- Permanent errors: bad payload → ACK ---
        try:
            payload = json.loads(message.data())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.logger.warning("tender_search.skip.bad_json", error=str(exc))
            return

        pk = payload.get("pk")
        if not pk:
            self.logger.warning("tender_search.skip.missing_pk")
            return

        title = (payload.get("title") or "").strip()
        if not title:
            self.logger.warning("tender_search.skip.empty_title", pk=pk)
            return

        # --- Transient errors: external calls → raise → NACK ---
        embedding = self.embedder.embed(title)

        record = {
            "pk":                    pk,
            "tender_id":             str(payload.get("tender_id") or "")[:64],
            "platform_id":           str(payload.get("platform_id") or "")[:256],
            "tender_national_id":    str(payload.get("tender_national_id") or "")[:256],
            "publication_date":      str(payload.get("publication_date") or "")[:32],
            "closing_date":          str(payload.get("closing_date") or "")[:32],
            "estimated_total_value": float(payload.get("estimated_total_value") or 0.0),
            "language_code":         str(payload.get("language_code") or "")[:16],
            "title":                 title[:65_535],
            "title_embedding":       embedding,
            "nut_code":              str(payload.get("nut_code") or "")[:32],
            "nut_label":             str(payload.get("nut_label") or "")[:256],
            "cpv_codes":             list(payload.get("cpv_codes") or []),
        }

        self.milvus.upsert(record)
        self.logger.info("tender_search.upserted",
                         pk=pk, language=record["language_code"],
                         title_len=len(title))
