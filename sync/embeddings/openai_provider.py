import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
from milvussync.logging import get_logger


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002") -> None:
        openai.api_key = api_key
        self.model = model
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(max=30),
        retry=retry_if_exception_type(openai.error.RateLimitError),
        reraise=True,
    )
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for the given text using the OpenAI old-style API."""
        response = openai.Embedding.create(model=self.model, input=text or "")
        return response["data"][0]["embedding"]
