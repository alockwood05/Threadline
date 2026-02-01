"""Embedder service for generating entry embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from threadline.models.embedding import EmbeddingModel, embedding_to_bytes
from threadline.ingest.models import Entry, EntryCreate


class Embedder:
    """Service for generating embeddings for entries."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: Path | None = None,
    ):
        """
        Initialize the embedder.

        Args:
            model_name: HuggingFace model name
            cache_dir: Directory to cache model files
        """
        self._embedding_model = EmbeddingModel(model_name, cache_dir)

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._embedding_model.model_name

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return self._embedding_model.dimensions

    def embed_text(self, text: str) -> bytes:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding as bytes (for database storage)
        """
        embedding = self._embedding_model.encode(text)
        return embedding_to_bytes(embedding)

    def embed_texts(
        self,
        texts: list[str],
        batch_size: int = 32,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[bytes]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of embeddings as bytes
        """
        if not texts:
            return []

        # Process in batches
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self._embedding_model.encode_batch(batch, batch_size)

            for embedding in batch_embeddings:
                all_embeddings.append(embedding_to_bytes(embedding))

            if progress_callback:
                progress_callback(min(i + batch_size, len(texts)), len(texts))

        return all_embeddings

    def embed_entries(
        self,
        entries: list[EntryCreate],
        batch_size: int = 32,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[EntryCreate]:
        """
        Add embeddings to entry objects.

        Args:
            entries: List of EntryCreate objects
            batch_size: Batch size for processing
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Same entries with embedding field populated
        """
        texts = [e.content for e in entries]
        embeddings = self.embed_texts(texts, batch_size, progress_callback)

        for entry, embedding in zip(entries, embeddings):
            entry.embedding = embedding

        return entries

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in memory."""
        return self._embedding_model.is_loaded()
