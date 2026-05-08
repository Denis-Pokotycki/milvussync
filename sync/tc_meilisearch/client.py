import meilisearch
import meilisearch.errors
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
    stop_after_attempt,
)
from milvussync.logging import get_logger

_INDEX_UID = "tender_translations"

_INDEX_SETTINGS = {
    "searchableAttributes": ["title", "nut_label", "nut_code"],
    "filterableAttributes": ["language_code", "nut_code"],
    "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
}

_TRANSIENT = (
    retry_if_exception_type(meilisearch.errors.MeilisearchCommunicationError)
    | retry_if_exception_type(ConnectionError)
)


class TenderSearchMeilisearchClient:
    def __init__(self, url: str, api_key: str = "") -> None:
        self._url = url
        self._api_key = api_key or None
        self._client: meilisearch.Client | None = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _get_client(self) -> meilisearch.Client:
        if self._client is None:
            self._client = meilisearch.Client(url=self._url, api_key=self._api_key)
        return self._client

    def _index(self):
        return self._get_client().index(_INDEX_UID)

    @retry(retry=_TRANSIENT, wait=wait_exponential_jitter(), stop=stop_after_attempt(3), reraise=True)
    def ensure_index(self) -> None:
        client = self._get_client()
        try:
            client.get_index(_INDEX_UID)
            self.logger.info("meilisearch.index_exists", index=_INDEX_UID)
        except meilisearch.errors.MeilisearchApiError as exc:
            if exc.status_code == 404:
                task = client.create_index(_INDEX_UID, {"primaryKey": "pk"})
                client.wait_for_task(task.task_uid)
                self.logger.info("meilisearch.index_created", index=_INDEX_UID)
            else:
                raise

        task = self._index().update_settings(_INDEX_SETTINGS)
        client.wait_for_task(task.task_uid)
        self.logger.info("meilisearch.settings_updated", index=_INDEX_UID)

    @retry(retry=_TRANSIENT, wait=wait_exponential_jitter(), stop=stop_after_attempt(3), reraise=True)
    def upsert_documents(self, documents: list[dict]) -> None:
        if not documents:
            return
        task = self._index().update_documents(documents, primary_key="pk")
        self.logger.debug("meilisearch.upsert_queued", count=len(documents), task_uid=task.task_uid)

    @retry(retry=_TRANSIENT, wait=wait_exponential_jitter(), stop=stop_after_attempt(3), reraise=True)
    def search(self, query: str, limit: int = 10) -> list[dict]:
        result = self._index().search(query, {"limit": limit, "showRankingScore": True})
        hits = result.get("hits", [])
        return [
            {**{k: v for k, v in hit.items() if not k.startswith("_")}, "meili_score": round(hit.get("_rankingScore", 0.0), 4)}
            for hit in hits
        ]

    def healthcheck(self) -> bool:
        try:
            return self._get_client().is_healthy()
        except Exception:
            return False
