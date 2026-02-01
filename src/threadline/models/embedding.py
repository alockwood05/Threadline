"""Embedding model wrapper for sentence-transformers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    """
    Wrapper for sentence-transformers embedding models.

    Supports lazy loading to avoid loading the model until needed.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: Path | None = None,
    ):
        """
        Initialize the embedding model.

        Args:
            model_name: HuggingFace model name or path
            cache_dir: Directory to cache model files
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model: "SentenceTransformer | None" = None
        self._dimensions: int | None = None

    @property
    def model(self) -> "SentenceTransformer":
        """Lazy load the model on first access."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            cache_folder = str(self.cache_dir) if self.cache_dir else None
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=cache_folder,
            )
            self._dimensions = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions, loading model if needed."""
        if self._dimensions is None:
            _ = self.model  # Trigger lazy load
        return self._dimensions  # type: ignore

    def encode(self, text: str) -> np.ndarray:
        """
        Encode a single text to embedding vector.

        Args:
            text: Text to encode

        Returns:
            Numpy array of shape (dimensions,)
        """
        return self.model.encode(text, convert_to_numpy=True)

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Encode multiple texts to embedding vectors.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding

        Returns:
            Numpy array of shape (len(texts), dimensions)
        """
        return self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > batch_size,
        )

    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._model is not None


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """
    Convert a numpy embedding array to bytes for storage.

    Args:
        embedding: Numpy array of float32 values

    Returns:
        Bytes representation
    """
    # Ensure float32
    embedding = embedding.astype(np.float32)
    return embedding.tobytes()


def bytes_to_embedding(data: bytes, dimensions: int = 384) -> np.ndarray:
    """
    Convert bytes back to numpy embedding array.

    Args:
        data: Bytes representation
        dimensions: Number of dimensions (for validation)

    Returns:
        Numpy array of float32 values
    """
    embedding = np.frombuffer(data, dtype=np.float32)
    if len(embedding) != dimensions:
        raise ValueError(
            f"Expected {dimensions} dimensions, got {len(embedding)}"
        )
    return embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity score (0 to 1)
    """
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))
