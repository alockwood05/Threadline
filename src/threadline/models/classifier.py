"""Zero-shot classifier model wrapper for transformers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import Pipeline


class ClassifierModel:
    """
    Wrapper for HuggingFace zero-shot classification models.

    Supports lazy loading to avoid loading the model until needed.
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        cache_dir: Path | None = None,
    ):
        """
        Initialize the classifier model.

        Args:
            model_name: HuggingFace model name or path
            cache_dir: Directory to cache model files
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._pipeline: "Pipeline | None" = None

    @property
    def pipeline(self) -> "Pipeline":
        """Lazy load the pipeline on first access."""
        if self._pipeline is None:
            from transformers import pipeline

            cache_folder = str(self.cache_dir) if self.cache_dir else None
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                model_kwargs={"cache_dir": cache_folder},
            )
        return self._pipeline

    def classify(
        self,
        text: str,
        candidate_labels: list[str],
    ) -> tuple[str, float]:
        """
        Classify a single text.

        Args:
            text: Text to classify
            candidate_labels: List of possible labels

        Returns:
            Tuple of (best_label, confidence_score)
        """
        result = self.pipeline(text, candidate_labels)
        return result["labels"][0], result["scores"][0]

    def classify_batch(
        self,
        texts: list[str],
        candidate_labels: list[str],
        batch_size: int = 8,
    ) -> list[tuple[str, float]]:
        """
        Classify multiple texts.

        Args:
            texts: List of texts to classify
            candidate_labels: List of possible labels
            batch_size: Batch size for processing

        Returns:
            List of (best_label, confidence_score) tuples
        """
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = self.pipeline(batch, candidate_labels)

            # Handle single vs batch results
            if isinstance(batch_results, dict):
                batch_results = [batch_results]

            for result in batch_results:
                results.append((result["labels"][0], result["scores"][0]))

        return results

    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._pipeline is not None
