from pymilvus import MilvusClient, DataType
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from milvussync.logging import get_logger

COLLECTION = "tender_search"
VECTOR_DIM = 1024


class TenderSearchMilvusClient:
    """
    Milvus client for the tender_search collection.

    Schema is translation-based: one entity per (tender_id, language_code) pair.
    The pk field is {tender_id}_{language_code} — deterministic, idempotent upserts.

    Index: HNSW + COSINE on title_embedding.
    COSINE is correct for normalized BGE embeddings (sentence-transformers
    normalizes with normalize_embeddings=True).

    CPV codes are stored as a Milvus ARRAY of VARCHAR so queries can use
    array_contains() for membership filtering.
    """

    def __init__(self, uri: str, token: str = "",
                 collection_name: str = COLLECTION,
                 vector_dim: int = VECTOR_DIM) -> None:
        self._uri = uri
        self._token = token or None
        self._collection_name = collection_name
        self._vector_dim = vector_dim
        self._client: MilvusClient | None = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _get_client(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(uri=self._uri, token=self._token)
        return self._client

    def ensure_collection(self) -> None:
        client = self._get_client()
        if client.has_collection(self._collection_name):
            self.logger.info("tender_search.collection_exists",
                             collection=self._collection_name)
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)

        schema.add_field("pk",                   DataType.VARCHAR, max_length=256, is_primary=True)
        schema.add_field("tender_id",            DataType.VARCHAR, max_length=64)
        schema.add_field("platform_id",          DataType.VARCHAR, max_length=256)
        schema.add_field("tender_national_id",   DataType.VARCHAR, max_length=256)
        schema.add_field("publication_date",     DataType.VARCHAR, max_length=32)
        schema.add_field("closing_date",         DataType.VARCHAR, max_length=32)
        schema.add_field("estimated_total_value",DataType.FLOAT)
        schema.add_field("language_code",        DataType.VARCHAR, max_length=16)
        schema.add_field("title",                DataType.VARCHAR, max_length=65_535)
        schema.add_field("title_embedding",      DataType.FLOAT_VECTOR, dim=self._vector_dim)
        schema.add_field("nut_code",             DataType.VARCHAR, max_length=32)
        schema.add_field("nut_label",            DataType.VARCHAR, max_length=256)
        schema.add_field(
            "cpv_codes",
            DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_capacity=20,
            max_length=32,
        )

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="title_embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )

        client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )
        self.logger.info("tender_search.collection_created",
                         collection=self._collection_name, dim=self._vector_dim)

    def drop_collection(self) -> None:
        client = self._get_client()
        if client.has_collection(self._collection_name):
            client.drop_collection(self._collection_name)
            self.logger.info("tender_search.collection_dropped",
                             collection=self._collection_name)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def upsert(self, record: dict) -> None:
        self._get_client().upsert(
            collection_name=self._collection_name,
            data=[record],
        )

    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        language_code: str | None = None,
        cpv_code: str | None = None,
        publication_date_gte: str | None = None,
    ) -> list[dict]:
        """
        Semantic search on title_embedding with optional scalar filters.

        Supported filters:
          language_code   — exact match, e.g. 'en'
          cpv_code        — array_contains(cpv_codes, '<code>')
          publication_date_gte — publication_date >= 'YYYY-MM-DD' (lexicographic,
                                  works because dates are stored as ISO-8601 strings)
        """
        filters = []
        if language_code:
            filters.append(f'language_code == "{language_code}"')
        if cpv_code:
            filters.append(f'array_contains(cpv_codes, "{cpv_code}")')
        if publication_date_gte:
            filters.append(f'publication_date >= "{publication_date_gte}"')

        filter_expr = " && ".join(filters)

        results = self._get_client().search(
            collection_name=self._collection_name,
            data=[query_embedding],
            anns_field="title_embedding",
            search_params={"metric_type": "COSINE", "params": {"ef": 100}},
            limit=limit,
            filter=filter_expr,
            output_fields=[
                "pk", "tender_id", "language_code", "title",
                "nut_code", "nut_label", "cpv_codes",
                "publication_date", "closing_date", "estimated_total_value",
            ],
        )

        hits = []
        for hit in results[0]:
            e = hit.entity
            hits.append({
                "pk":                    e.get("pk"),
                "tender_id":             e.get("tender_id"),
                "language_code":         e.get("language_code"),
                "title":                 e.get("title"),
                "nut_code":              e.get("nut_code"),
                "nut_label":             e.get("nut_label"),
                "cpv_codes":             e.get("cpv_codes", []),
                "publication_date":      e.get("publication_date"),
                "closing_date":          e.get("closing_date"),
                "estimated_total_value": e.get("estimated_total_value"),
                "score":                 hit.score,
            })
        return hits

    def count(self) -> int:
        try:
            result = self._get_client().query(
                collection_name=self._collection_name,
                filter='pk != ""',
                output_fields=["count(*)"],
            )
            return result[0].get("count(*)", 0) if result else 0
        except Exception:
            return 0

    def list_records(self, limit: int = 100) -> list[dict]:
        try:
            rows = self._get_client().query(
                collection_name=self._collection_name,
                filter='pk != ""',
                output_fields=[
                    "pk", "tender_id", "platform_id", "tender_national_id",
                    "publication_date", "closing_date", "estimated_total_value",
                    "language_code", "title",
                    "nut_code", "nut_label", "cpv_codes",
                ],
                limit=limit,
            )
            return rows or []
        except Exception:
            return []

    def healthcheck(self) -> bool:
        try:
            self._get_client().list_collections()
            return True
        except Exception:
            return False
