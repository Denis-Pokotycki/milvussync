from milvussync.logging import get_logger


class BGERerankerProvider:
    """
    Cross-encoder reranker using BAAI/bge-reranker-base (or -large).

    Usage:
        reranker = BGERerankerProvider()
        results  = reranker.rerank(query, candidate_records, limit=10)

    Input records must have a "title" field.
    Output records gain a "rerank_score" float (higher = more relevant).
    The model outputs raw logits (unbounded); typical range is roughly -10 to +10.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        self._model_name = model_name
        self._model = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self.logger.info("reranker.loading_model", model=self._model_name)
            self._model = CrossEncoder(self._model_name)
            self.logger.info("reranker.model_ready", model=self._model_name)
        return self._model

    def rerank(
        self,
        query: str,
        records: list[dict],
        text_field: str = "title",
        limit: int = 10,
    ) -> list[dict]:
        """Score each (query, record[text_field]) pair and return top `limit`."""
        if not records:
            return []

        model = self._get_model()
        pairs = [[query, (r.get(text_field) or "")] for r in records]
        scores = model.predict(pairs)

        ranked = sorted(
            zip(records, scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            {**r, "rerank_score": round(float(s), 4)}
            for r, s in ranked[:limit]
        ]
