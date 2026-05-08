"""
In-memory fakes for Milvus clients.

FakeMilvusClient  — original, keyed by platform_id (legacy tenders collection)
FakeTenderSearchClient — keyed by pk (tender_search collection)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── Legacy TenderMilvusClient fake ──────────────────────────────────────────

last_client: "FakeMilvusClient | None" = None


def reset() -> None:
    global last_client
    last_client = None


class FakeMilvusClient:
    def __init__(
        self,
        uri: str = "http://localhost:19530",
        token: str = "",
        collection_name: str = "tenders",
        vector_dim: int = 1536,
    ) -> None:
        self._collection_name = collection_name
        self._records: Dict[str, Dict[str, Any]] = {}
        self._collection_ensured = False
        global last_client
        last_client = self

    def ensure_collection(self) -> None:
        self._collection_ensured = True

    def upsert(self, record: dict) -> None:
        self._records[record["platform_id"]] = record

    def healthcheck(self) -> bool:
        return True

    # --- helpers for tests ---
    def get_record(self, platform_id: str) -> Optional[Dict[str, Any]]:
        return self._records.get(platform_id)

    def all_records(self) -> List[Dict[str, Any]]:
        return list(self._records.values())

    def record_count(self) -> int:
        return len(self._records)


# ── TenderSearchMilvusClient fake ────────────────────────────────────────────

last_search_client: "FakeTenderSearchClient | None" = None


def reset_search() -> None:
    global last_search_client
    last_search_client = None


class FakeTenderSearchClient:
    """In-memory fake for TenderSearchMilvusClient. Keyed by pk field."""

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        token: str = "",
        collection_name: str = "tender_search",
        vector_dim: int = 1024,
    ) -> None:
        self._collection_name = collection_name
        self._records: Dict[str, Dict[str, Any]] = {}
        self._collection_ensured = False
        self._dropped = False
        global last_search_client
        last_search_client = self

    def ensure_collection(self) -> None:
        self._collection_ensured = True

    def drop_collection(self) -> None:
        self._dropped = True
        self._records.clear()

    def upsert(self, record: dict) -> None:
        self._records[record["pk"]] = record

    def search(
        self,
        query_embedding: list,
        limit: int = 10,
        language_code: str | None = None,
        cpv_code: str | None = None,
        publication_date_gte: str | None = None,
    ) -> list[dict]:
        results = []
        for rec in self._records.values():
            if language_code and rec.get("language_code") != language_code:
                continue
            if cpv_code and cpv_code not in rec.get("cpv_codes", []):
                continue
            if publication_date_gte and rec.get("publication_date", "") < publication_date_gte:
                continue
            results.append({**rec, "score": 0.99})
        return results[:limit]

    def healthcheck(self) -> bool:
        return True

    # --- helpers for tests ---
    def get_record(self, pk: str) -> Optional[Dict[str, Any]]:
        return self._records.get(pk)

    def all_records(self) -> List[Dict[str, Any]]:
        return list(self._records.values())

    def record_count(self) -> int:
        return len(self._records)
