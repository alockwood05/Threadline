"""Classifier service for categorizing entries."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from threadline.models.classifier import ClassifierModel
from threadline.ingest.models import EntryCreate


class Classifier:
    """Service for classifying entry types."""

    DEFAULT_LABELS = [
        "thought",
        "todo list",
        "summary",
        "bullet list",
        "prayer",
        "reflection",
        "question",
    ]

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        labels: list[str] | None = None,
        confidence_threshold: float = 0.6,
        cache_dir: Path | None = None,
    ):
        """
        Initialize the classifier.

        Args:
            model_name: HuggingFace model name
            labels: List of candidate labels for classification
            confidence_threshold: Below this, mark as 'uncertain'
            cache_dir: Directory to cache model files
        """
        self._classifier_model = ClassifierModel(model_name, cache_dir)
        self.labels = labels or self.DEFAULT_LABELS
        self.confidence_threshold = confidence_threshold

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._classifier_model.model_name

    def classify_text(self, text: str) -> tuple[str, float]:
        """
        Classify a single text.

        Args:
            text: Text to classify

        Returns:
            Tuple of (entry_type, confidence)
        """
        return self._classifier_model.classify(text, self.labels)

    def classify_texts(
        self,
        texts: list[str],
        batch_size: int = 8,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Classify multiple texts.

        Args:
            texts: List of texts to classify
            batch_size: Batch size for processing
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of (entry_type, confidence) tuples
        """
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = self._classifier_model.classify_batch(
                batch, self.labels, batch_size
            )
            results.extend(batch_results)

            if progress_callback:
                progress_callback(min(i + batch_size, len(texts)), len(texts))

        return results

    def classify_entries(
        self,
        entries: list[EntryCreate],
        batch_size: int = 8,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[EntryCreate]:
        """
        Add classification to entry objects.

        Args:
            entries: List of EntryCreate objects
            batch_size: Batch size for processing
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Same entries with entry_type and entry_type_confidence populated
        """
        texts = [e.content for e in entries]
        classifications = self.classify_texts(texts, batch_size, progress_callback)

        for entry, (entry_type, confidence) in zip(entries, classifications):
            entry.entry_type = entry_type
            entry.entry_type_confidence = confidence

        return entries

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in memory."""
        return self._classifier_model.is_loaded()
