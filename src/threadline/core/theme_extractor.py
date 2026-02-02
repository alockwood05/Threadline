"""Theme extraction service using BERTopic."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    from bertopic import BERTopic


@dataclass
class ExtractedTopic:
    """A topic extracted by BERTopic."""

    topic_id: int  # BERTopic's topic number (-1 = outliers)
    name: str  # Auto-generated name from top keywords
    keywords: list[dict[str, float]]  # List of {"word": str, "weight": float}
    representative_doc_indices: list[int]  # Indices into the original documents list
    entry_count: int


@dataclass
class ThemeExtractionOutput:
    """Output of theme extraction."""

    topics: list[ExtractedTopic]
    # assignments[i] = (topic_id, probability) for document at index i
    assignments: list[tuple[int, float]]


class ThemeExtractor:
    """
    Service for extracting themes from entries using BERTopic.

    Uses pre-computed embeddings (from ingestion) to avoid re-encoding.
    Pipeline: embeddings -> UMAP -> HDBSCAN -> c-TF-IDF -> topic keywords
    """

    def __init__(
        self,
        min_topic_size: int = 5,
        nr_topics: str | int = "auto",
    ):
        """
        Initialize the theme extractor.

        Args:
            min_topic_size: Minimum number of entries required to form a topic.
                           Lower = more granular topics, higher = fewer, broader topics.
            nr_topics: Number of topics to extract. "auto" lets HDBSCAN decide.
                      Can also be an integer to force a specific number.
        """
        self.min_topic_size = min_topic_size
        self.nr_topics = nr_topics
        self._model: "BERTopic | None" = None

    @property
    def model(self) -> "BERTopic":
        """Lazy-load BERTopic model on first access."""
        if self._model is None:
            self._model = self._create_model()
        return self._model

    def _create_model(self) -> "BERTopic":
        """Create and configure BERTopic model."""
        try:
            from bertopic import BERTopic
            from umap import UMAP
            from hdbscan import HDBSCAN
        except ImportError as e:
            raise ImportError(
                "Theme extraction requires BERTopic. "
                "Install with: pip install threadline[ml-full]"
            ) from e

        # Configure UMAP for dimensionality reduction
        # Lower n_neighbors for smaller datasets
        umap_model = UMAP(
            n_neighbors=15,
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=42,
        )

        # Configure HDBSCAN for clustering
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.min_topic_size,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )

        # Create BERTopic with our custom UMAP and HDBSCAN
        # We pass embeddings directly, so no need for embedding model
        model = BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            nr_topics=self.nr_topics if self.nr_topics != "auto" else None,
            top_n_words=10,
            verbose=False,
        )

        return model

    def extract_themes(
        self,
        documents: list[str],
        embeddings: np.ndarray,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ThemeExtractionOutput:
        """
        Extract themes from documents using pre-computed embeddings.

        Args:
            documents: List of document texts (for keyword extraction)
            embeddings: Pre-computed embeddings array of shape (n_docs, embedding_dim)
            progress_callback: Optional callback(stage, current, total) for progress

        Returns:
            ThemeExtractionOutput with topics and assignments
        """
        if len(documents) != embeddings.shape[0]:
            raise ValueError(
                f"Mismatch: {len(documents)} documents but {embeddings.shape[0]} embeddings"
            )

        if len(documents) < self.min_topic_size:
            raise ValueError(
                f"Need at least {self.min_topic_size} documents for theme extraction, "
                f"got {len(documents)}"
            )

        if progress_callback:
            progress_callback("Running UMAP + HDBSCAN clustering", 0, 3)

        # Run BERTopic fit_transform with pre-computed embeddings
        topics, probabilities = self.model.fit_transform(documents, embeddings)

        if progress_callback:
            progress_callback("Extracting topic keywords", 1, 3)

        # Get topic info
        topic_info = self.model.get_topic_info()

        # Build assignments list
        # probabilities might be a 2D array (soft clustering) or None
        if probabilities is None or len(probabilities.shape) == 1:
            # Hard clustering - just use the assigned topic with prob 1.0
            assignments = [(int(t), 1.0 if t != -1 else 0.0) for t in topics]
        else:
            # Soft clustering - get the probability for the assigned topic
            assignments = []
            for i, topic_id in enumerate(topics):
                if topic_id == -1:
                    prob = 0.0
                else:
                    # Find the column index for this topic_id
                    topic_col_idx = topic_id + 1  # topic -1 is index 0
                    if topic_col_idx < probabilities.shape[1]:
                        prob = float(probabilities[i, topic_col_idx])
                    else:
                        prob = 1.0
                assignments.append((int(topic_id), prob))

        if progress_callback:
            progress_callback("Building topic summaries", 2, 3)

        # Build topics list
        extracted_topics = []
        for _, row in topic_info.iterrows():
            topic_id = int(row["Topic"])

            # Get top keywords for this topic
            if topic_id == -1:
                # Outlier topic
                keywords = []
                name = "Outliers"
            else:
                topic_words = self.model.get_topic(topic_id)
                if topic_words:
                    keywords = [
                        {"word": word, "weight": float(weight)}
                        for word, weight in topic_words
                    ]
                    # Generate name from top 3 keywords
                    top_words = [kw["word"] for kw in keywords[:3]]
                    name = "_".join(top_words)
                else:
                    keywords = []
                    name = f"Topic_{topic_id}"

            # Get representative documents (indices)
            rep_docs = self.model.get_representative_docs(topic_id) if topic_id != -1 else []
            # Find indices of these representative docs in original documents list
            rep_indices = []
            for doc in rep_docs or []:
                try:
                    idx = documents.index(doc)
                    rep_indices.append(idx)
                except ValueError:
                    pass

            # Count entries in this topic
            entry_count = int(row["Count"]) if "Count" in row else sum(
                1 for t in topics if t == topic_id
            )

            extracted_topics.append(
                ExtractedTopic(
                    topic_id=topic_id,
                    name=name,
                    keywords=keywords,
                    representative_doc_indices=rep_indices[:5],  # Limit to 5
                    entry_count=entry_count,
                )
            )

        if progress_callback:
            progress_callback("Theme extraction complete", 3, 3)

        return ThemeExtractionOutput(
            topics=extracted_topics,
            assignments=assignments,
        )

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in memory."""
        return self._model is not None


def keywords_to_json(keywords: list[dict[str, float]]) -> str:
    """Convert keywords list to JSON string for storage."""
    return json.dumps(keywords)


def json_to_keywords(json_str: str | None) -> list[dict[str, float]]:
    """Parse keywords JSON string back to list."""
    if not json_str:
        return []
    return json.loads(json_str)


def entry_ids_to_json(entry_ids: list[int]) -> str:
    """Convert entry IDs list to JSON string for storage."""
    return json.dumps(entry_ids)


def json_to_entry_ids(json_str: str | None) -> list[int]:
    """Parse entry IDs JSON string back to list."""
    if not json_str:
        return []
    return json.loads(json_str)
