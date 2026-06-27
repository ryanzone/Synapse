"""
Embedding service for Synapse backend.

Uses LM Studio's OpenAI-compatible embeddings endpoint to generate
dense vector representations of text using the Nomic Embed Text model.
"""

from __future__ import annotations

from typing import Optional

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Async embedding service backed by LM Studio / Nomic Embed Text.

    Generates fixed-dimensional float vectors suitable for semantic
    similarity search in Qdrant.

    Args:
        settings: Application settings.  Defaults to the global singleton.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncOpenAI(
            base_url=self._settings.lmstudio_base_url,
            api_key=self._settings.lmstudio_api_key,
        )
        logger.info(
            "EmbeddingService initialised — model={}",
            self._settings.embedding_model,
        )

    async def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: The text to embed.  Leading/trailing whitespace is stripped.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            ValueError: If the text is empty after stripping.
            openai.APIError: If the LM Studio API returns an error.
        """
        text = text.strip()
        if not text:
            raise ValueError("Cannot embed an empty string.")

        logger.debug(
            "embed() — model={} text_len={}",
            self._settings.embedding_model,
            len(text),
        )

        response = await self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=text,
        )
        vector: list[float] = response.data[0].embedding
        logger.debug("embed() — vector_dim={}", len(vector))
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of text strings in a single API call.

        Args:
            texts: Non-empty list of texts to embed.

        Returns:
            A list of embedding vectors, one per input text, in order.

        Raises:
            ValueError: If the texts list is empty.
            openai.APIError: If the LM Studio API returns an error.
        """
        if not texts:
            raise ValueError("texts list must not be empty.")

        stripped = [t.strip() for t in texts]
        if any(not t for t in stripped):
            raise ValueError("All texts in the batch must be non-empty strings.")

        logger.debug(
            "embed_batch() — model={} batch_size={}",
            self._settings.embedding_model,
            len(stripped),
        )

        response = await self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=stripped,
        )

        # The API guarantees ordering matches the input list
        vectors: list[list[float]] = [item.embedding for item in response.data]
        logger.debug(
            "embed_batch() — returned={} vector_dim={}",
            len(vectors),
            len(vectors[0]) if vectors else 0,
        )
        return vectors

    async def similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute the cosine similarity between two text strings.

        Args:
            text_a: First text.
            text_b: Second text.

        Returns:
            Cosine similarity in the range [-1.0, 1.0].
        """
        vectors = await self.embed_batch([text_a, text_b])
        return _cosine_similarity(vectors[0], vectors[1])


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors without numpy.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity value.

    Raises:
        ValueError: If vectors have different lengths or are zero-length.
    """
    if len(a) != len(b):
        raise ValueError(
            f"Vector dimension mismatch: {len(a)} vs {len(b)}"
        )
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)