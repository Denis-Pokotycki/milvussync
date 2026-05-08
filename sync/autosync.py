"""
Background auto-sync daemon: polls PostgreSQL for new/updated rows, generates BGE
embeddings, and upserts into Milvus and Meilisearch.

Started as a daemon thread by SyncConfig.ready(). Survives indefinitely; interval
and state cursor are configurable via settings.
"""
import json
import os
import threading
import time
from datetime import datetime

from milvussync.logging import get_logger

logger = get_logger(__name__)

_thread: threading.Thread | None = None


def _load_state(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _build_record(row: dict, embedding: list[float]) -> dict:
    """Map a PostgreSQL row + embedding into the Milvus/Meilisearch document shape."""
    return {
        "pk":                    row["pk"],
        "tender_id":             str(row.get("tender_id") or "")[:64],
        "platform_id":           str(row.get("platform_id") or "")[:256],
        "tender_national_id":    str(row.get("tender_national_id") or "")[:256],
        "publication_date":      str(row.get("publication_date") or "")[:32],
        "closing_date":          str(row.get("closing_date") or "")[:32],
        "estimated_total_value": float(row.get("estimated_total_value") or 0.0),
        "language_code":         str(row.get("language_code") or "")[:16],
        "title":                 (row.get("title") or "").strip()[:65_535],
        "title_embedding":       embedding,
        "nut_code":              str(row.get("nut_code") or "")[:32],
        "nut_label":             str(row.get("nut_label") or "")[:256],
        "cpv_codes":             list(row.get("cpv_codes") or []),
    }


def _sync_pass(repo, embedder, milvus, state_path: str, meili=None) -> int:
    state = _load_state(state_path)
    since = state.get("last_synced_at")

    total = repo.count(since=since)
    if total == 0:
        return 0

    logger.info("autosync.pass_start", total=total, since=since)
    synced = 0
    latest_ts: str | None = None
    meili_batch: list[dict] = []

    rows = repo.fetch_page(offset=0, limit=total, since=since)
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            continue

        try:
            embedding = embedder.embed(title)
        except Exception as exc:
            logger.warning("autosync.embed_error", pk=row["pk"], error=str(exc))
            continue

        record = _build_record(row, embedding)

        try:
            milvus.upsert(record)
            synced += 1
            row_ts = row.get("updated_at")
            if row_ts is not None:
                if isinstance(row_ts, datetime):
                    row_ts = row_ts.isoformat()
                latest_ts = str(row_ts)
            if meili is not None:
                meili_batch.append({k: v for k, v in record.items() if k != "title_embedding"})
        except Exception as exc:
            logger.warning("autosync.upsert_error", pk=row["pk"], error=str(exc))

    if meili is not None and meili_batch:
        try:
            meili.upsert_documents(meili_batch)
        except Exception as exc:
            logger.warning("autosync.meili_upsert_error", count=len(meili_batch), error=str(exc))

    if latest_ts:
        state["last_synced_at"] = latest_ts
        _save_state(state_path, state)

    logger.info("autosync.pass_done", synced=synced)
    return synced


def _run_loop(interval: int, state_path: str) -> None:
    from django.conf import settings
    from sync.postgres.tender_repository import TenderTranslationRepository
    from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient
    from sync.tc_meilisearch.client import TenderSearchMeilisearchClient
    from sync.embeddings.bge_provider import BGEEmbeddingProvider

    logger.info("autosync.thread_started", interval_s=interval)

    try:
        repo = TenderTranslationRepository()
        milvus = TenderSearchMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.TENDER_SEARCH_COLLECTION,
            vector_dim=settings.TENDER_SEARCH_VECTOR_DIM,
        )
        milvus.ensure_collection()
        embedder = BGEEmbeddingProvider(settings.EMBEDDING_MODEL_NAME)
        logger.info("autosync.initialized")
    except Exception as exc:
        logger.error("autosync.init_failed", error=str(exc))
        return

    meili = TenderSearchMeilisearchClient(
        url=settings.MEILISEARCH_URL,
        api_key=settings.MEILISEARCH_API_KEY,
    )
    try:
        meili.ensure_index()
        logger.info("autosync.meili_initialized")
    except Exception as exc:
        logger.warning("autosync.meili_init_failed", error=str(exc))
        meili = None

    while True:
        try:
            _sync_pass(repo, embedder, milvus, state_path, meili=meili)
        except Exception as exc:
            logger.error("autosync.loop_error", error=str(exc))
        time.sleep(interval)


def start(interval: int, state_path: str) -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(
        target=_run_loop,
        args=(interval, state_path),
        daemon=True,
        name="milvussync-autosync",
    )
    _thread.start()


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()
