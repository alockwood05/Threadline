"""Ingestion pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from threadline.config.paths import get_originals_dir, get_models_dir
from threadline.config.settings import Settings
from threadline.db.connection import Database
from threadline.db.repositories.sources import SourceRepository
from threadline.db.repositories.entries import EntryRepository
from threadline.ingest.file_scanner import scan_path, copy_to_originals
from threadline.ingest.markdown import parse_markdown_file
from threadline.ingest.models import (
    IngestResult,
    SourceCreate,
    EntryCreate,
    ScannedFile,
    ParsedDocument,
)
from threadline.core.chunker import (
    chunk_text,
    generate_summary_quote,
    generate_title_from_content,
)
from threadline.core.embedder import Embedder
from threadline.core.classifier import EntryClassifier


class IngestPipeline:
    """
    Orchestrates the full ingestion pipeline.

    Pipeline stages:
    1. Scan for files
    2. Filter duplicates (by hash)
    3. Copy to originals/
    4. Parse content (markdown)
    5. Chunk into entries
    6. Generate titles/summaries
    7. Classify entries
    8. Generate embeddings
    9. Store in database
    """

    def __init__(
        self,
        db: Database,
        settings: Settings,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        """
        Initialize the pipeline.

        Args:
            db: Database connection
            settings: Application settings
            progress_callback: Optional callback(stage, current, total)
        """
        self.db = db
        self.settings = settings
        self.progress_callback = progress_callback

        self.source_repo = SourceRepository(db.conn)
        self.entry_repo = EntryRepository(db.conn)
        self.originals_dir = get_originals_dir()
        self.models_dir = get_models_dir()

        # Lazy-loaded embedder and classifier
        self._embedder: Embedder | None = None
        self._classifier: EntryClassifier | None = None

    @property
    def embedder(self) -> Embedder:
        """Lazy load embedder."""
        if self._embedder is None:
            self._embedder = Embedder(
                model_name=self.settings.embeddings.model,
                cache_dir=self.models_dir,
            )
        return self._embedder

    @property
    def classifier(self) -> EntryClassifier:
        """Lazy load classifier."""
        if self._classifier is None:
            self._classifier = EntryClassifier(
                model_name=self.settings.classification.model,
                labels=self.settings.classification.labels,
                confidence_threshold=self.settings.classification.confidence_threshold,
                cache_dir=self.models_dir,
            )
        return self._classifier

    def ingest_path(
        self,
        path: Path,
        generate_embeddings: bool = True,
        classify_entries: bool = True,
        min_chunk_chars: int = 30,
    ) -> IngestResult:
        """
        Ingest files from a path.

        Args:
            path: File or directory to ingest
            generate_embeddings: Whether to generate embeddings
            classify_entries: Whether to classify entry types
            min_chunk_chars: Minimum characters for a chunk

        Returns:
            IngestResult with counts and any errors
        """
        result = IngestResult()

        # Stage 1: Scan for files
        self._report_progress("Scanning files", 0, 1)
        scanned_files = list(scan_path(path))
        total_files = len(scanned_files)

        if total_files == 0:
            result.errors.append(f"No supported files found in {path}")
            return result

        # Stage 2-7: Process each file
        all_entries: list[EntryCreate] = []

        for i, scanned in enumerate(scanned_files):
            self._report_progress("Processing files", i, total_files)

            try:
                entries = self._process_file(scanned, min_chunk_chars, result)
                all_entries.extend(entries)
            except Exception as e:
                result.files_failed += 1
                result.errors.append(f"{scanned.filename}: {str(e)}")

        # Stage 8: Classify entries in batch
        if classify_entries and all_entries:
            self._report_progress("Classifying entries", 0, len(all_entries))

            def classification_progress(current: int, total: int) -> None:
                self._report_progress("Classifying entries", current, total)

            self.classifier.classify_entries(
                all_entries,
                batch_size=8,
                progress_callback=classification_progress,
            )

        # Stage 9: Generate embeddings in batch
        if generate_embeddings and all_entries:
            self._report_progress("Generating embeddings", 0, len(all_entries))

            def embedding_progress(current: int, total: int) -> None:
                self._report_progress("Generating embeddings", current, total)

            self.embedder.embed_entries(
                all_entries,
                batch_size=32,
                progress_callback=embedding_progress,
            )

        # Stage 9: Store entries
        if all_entries:
            self._report_progress("Storing entries", 0, len(all_entries))
            for i, entry in enumerate(all_entries):
                self.entry_repo.create(entry)
                result.entries_created += 1
                if i % 10 == 0:
                    self._report_progress("Storing entries", i, len(all_entries))

        self._report_progress("Complete", total_files, total_files)
        return result

    def _process_file(
        self,
        scanned: ScannedFile,
        min_chunk_chars: int,
        result: IngestResult,
    ) -> list[EntryCreate]:
        """Process a single file through the pipeline."""
        # Check for duplicate
        if self.source_repo.exists_by_hash(scanned.file_hash):
            result.files_skipped += 1
            return []

        # Copy to originals
        relative_path = copy_to_originals(
            scanned.path,
            self.originals_dir,
        )

        # Parse content
        if scanned.file_type == "markdown":
            parsed = parse_markdown_file(scanned.path)
        else:
            # Image - skip for MVP (no OCR yet)
            result.files_skipped += 1
            return []

        # Create source record
        source = SourceCreate(
            filename=scanned.filename,
            filepath=str(relative_path),
            file_hash=scanned.file_hash,
            file_type=scanned.file_type,
            raw_text=parsed.raw_text,
        )
        source_id = self.source_repo.create(source)
        result.files_imported += 1

        # Chunk into entries
        chunks = chunk_text(parsed.raw_text, min_chars=min_chunk_chars)

        if not chunks:
            return []

        # Create entry objects
        entries: list[EntryCreate] = []
        entry_date_str = parsed.date.isoformat() if parsed.date else None

        for chunk in chunks:
            title = generate_title_from_content(
                chunk.content,
                entry_date=entry_date_str,
                location=parsed.location,
            )
            summary = generate_summary_quote(chunk.content)

            entry = EntryCreate(
                source_id=source_id,
                content=chunk.content,
                title=title,
                entry_date=parsed.date,
                location=parsed.location,
                summary_quote=summary,
                source_line_start=chunk.line_start,
                source_line_end=chunk.line_end,
                # embedding and entry_type added later in batch
            )
            entries.append(entry)

        return entries

    def _report_progress(self, stage: str, current: int, total: int) -> None:
        """Report progress via callback if set."""
        if self.progress_callback:
            self.progress_callback(stage, current, total)
