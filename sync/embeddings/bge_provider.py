from milvussync.logging import get_logger


class BGEEmbeddingProvider:
    """
    Embedding provider using BAAI/bge-large-en-v1.5 via sentence-transformers.

    Dimension: 1024. Embeddings are L2-normalized, so cosine similarity equals
    dot product — use COSINE or IP metric in Milvus.

    For indexing (passages): call embed(text) — no instruction prefix.
    For querying: call embed_query(query) — prepends the BGE retrieval instruction.
    """

    _QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        self._model_name = model_name
        self._model = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _get_model(self):
        if self._model is None:
            # Import here so tests can mock before the model loads
            from sentence_transformers import SentenceTransformer
            self.logger.info("bge.loading_model", model=self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Embed a tender title for indexing (no instruction prefix)."""
        return self._get_model().encode(text or "", normalize_embeddings=True).tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query (adds BGE retrieval instruction prefix)."""
        prefixed = self._QUERY_INSTRUCTION + (query or "")
        return self._get_model().encode(prefixed, normalize_embeddings=True).tolist()

    @property
    def dim(self) -> int:
        return 1024
