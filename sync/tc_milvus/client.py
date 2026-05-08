from pymilvus import MilvusClient, DataType
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
from milvussync.logging import get_logger


class TenderMilvusClient:
    def __init__(
        self,
        uri: str,
        token: str,
        collection_name: str,
        vector_dim: int,
    ) -> None:
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
        """Create the tenders collection and index if not present. Idempotent."""
        client = self._get_client()
        if client.has_collection(self._collection_name):
            self.logger.info(
                "milvus.collection_exists", collection=self._collection_name
            )
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="platform_id",
            datatype=DataType.VARCHAR,
            max_length=256,
            is_primary=True,
        )
        schema.add_field(
            field_name="title",
            datatype=DataType.VARCHAR,
            max_length=65_535,
        )
        schema.add_field(
            field_name="title_embedding",
            datatype=DataType.FLOAT_VECTOR,
            dim=self._vector_dim,
        )
        schema.add_field(
            field_name="country_id",
            datatype=DataType.VARCHAR,
            max_length=16,
        )
        schema.add_field(
            field_name="cpv",
            datatype=DataType.VARCHAR,
            max_length=64,
        )
        schema.add_field(
            field_name="procedure_type",
            datatype=DataType.VARCHAR,
            max_length=128,
        )
        schema.add_field(
            field_name="publication_date",
            datatype=DataType.VARCHAR,
            max_length=32,
        )
        schema.add_field(
            field_name="closing_date",
            datatype=DataType.VARCHAR,
            max_length=32,
        )
        schema.add_field(
            field_name="synced_at",
            datatype=DataType.INT64,
        )

        # HNSW + COSINE: correct choice for ada-002 unit-normalized vectors
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
        self.logger.info(
            "milvus.collection_created", collection=self._collection_name
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def upsert(self, record: dict) -> None:
        """Upsert a single tender record. Idempotent via platform_id primary key."""
        self._get_client().upsert(
            collection_name=self._collection_name,
            data=[record],
        )

    def healthcheck(self) -> bool:
        try:
            return self._get_client().has_collection(self._collection_name)
        except Exception:
            return False

    def count(self) -> int:
        try:
            client = self._get_client()
            if not client.has_collection(self._collection_name):
                return 0
            stats = client.get_collection_stats(self._collection_name)
            return int(stats.get("row_count", 0))
        except Exception:
            return 0

    def list_records(self, limit: int = 100) -> list[dict]:
        try:
            client = self._get_client()
            if not client.has_collection(self._collection_name):
                return []

            # Inspect the real schema so we never query fields that don't exist
            info = client.describe_collection(self._collection_name)
            vector_types = {DataType.FLOAT_VECTOR, DataType.BINARY_VECTOR}
            scalar_fields = [
                f["name"] for f in info.get("fields", [])
                if f.get("type") not in vector_types
            ]

            # Build a type-correct filter on the primary key field
            pk = next(
                (f for f in info.get("fields", []) if f.get("is_primary")),
                None,
            )
            if pk is None:
                return []
            if pk.get("type") == DataType.VARCHAR:
                filter_expr = f'{pk["name"]} != ""'
            else:
                filter_expr = f'{pk["name"]} >= 0'

            rows = client.query(
                collection_name=self._collection_name,
                filter=filter_expr,
                output_fields=scalar_fields,
                limit=limit,
            )
            return sorted(rows, key=lambda r: r.get("synced_at", 0), reverse=True)
        except Exception:
            return []
