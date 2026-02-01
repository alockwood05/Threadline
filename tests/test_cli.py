"""Regression tests for Threadline CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from threadline.cli.main import app


runner = CliRunner()


class TestInit:
    """Tests for `threadline init` command."""

    def test_init_creates_directory_structure(
        self, tmp_threadline_home: Path
    ) -> None:
        """threadline init creates expected directory structure and files."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, f"Init failed: {result.output}"

        # Verify directory structure
        assert tmp_threadline_home.exists(), "Threadline home not created"
        assert (tmp_threadline_home / "originals").exists(), "originals dir not created"
        assert (tmp_threadline_home / "models").exists(), "models dir not created"
        assert (tmp_threadline_home / "backups").exists(), "backups dir not created"

        # Verify database created
        assert (tmp_threadline_home / "threadline.db").exists(), "Database not created"

        # Verify config created
        assert (tmp_threadline_home / "config.yaml").exists(), "Config not created"

    def test_init_idempotent_with_force(
        self, tmp_threadline_home: Path
    ) -> None:
        """threadline init --force can reinitialize."""
        # First init
        result1 = runner.invoke(app, ["init"])
        assert result1.exit_code == 0

        # Second init without force should fail
        result2 = runner.invoke(app, ["init"])
        assert result2.exit_code == 1

        # Second init with force should succeed
        result3 = runner.invoke(app, ["init", "--force"])
        assert result3.exit_code == 0


class TestIngestMarkdown:
    """Tests for `threadline ingest` with markdown files."""

    def test_ingest_markdown_creates_source_and_entries(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """threadline ingest successfully imports a markdown file."""
        result = runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        assert result.exit_code == 0, f"Ingest failed: {result.output}"
        assert "Files imported: 1" in result.output

        # Verify database state
        from threadline.db.connection import Database
        from threadline.db.repositories.sources import SourceRepository
        from threadline.db.repositories.entries import EntryRepository

        db = Database(initialized_threadline / "threadline.db")
        source_repo = SourceRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        # Check source was created
        sources = source_repo.list()
        assert len(sources) == 1, "Expected 1 source"
        assert sources[0].file_type == "markdown"

        # Check entries were created from chunks
        entries = entry_repo.list()
        assert len(entries) > 0, "Expected entries to be created"

        db.close()

    def test_ingest_copies_original_file(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """threadline ingest copies original file to originals directory."""
        result = runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        assert result.exit_code == 0

        # Check file was copied to originals
        originals_dir = initialized_threadline / "originals"
        original_files = list(originals_dir.rglob("*.md"))
        assert len(original_files) == 1, "Original file not copied"


class TestIngestSkipDuplicates:
    """Tests for duplicate detection during ingestion."""

    def test_ingest_skips_duplicate_file(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Re-ingesting same file skips it (by hash)."""
        # First ingest
        result1 = runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])
        assert result1.exit_code == 0
        assert "Files imported: 1" in result1.output

        # Second ingest should skip
        result2 = runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])
        assert result2.exit_code == 0
        assert "Files imported: 0" in result2.output
        assert "Files skipped: 1" in result2.output

        # Verify only one source in database
        from threadline.db.connection import Database
        from threadline.db.repositories.sources import SourceRepository

        db = Database(initialized_threadline / "threadline.db")
        source_repo = SourceRepository(db.conn)
        assert source_repo.count() == 1, "Duplicate source was created"
        db.close()


class TestIngestDirectory:
    """Tests for recursive directory ingestion."""

    def test_ingest_directory_recursive(
        self, initialized_threadline: Path, sample_markdown_directory: Path
    ) -> None:
        """threadline ingest <dir> recursively finds and imports files."""
        result = runner.invoke(
            app, ["ingest", str(sample_markdown_directory), "--no-embeddings"]
        )

        assert result.exit_code == 0, f"Ingest failed: {result.output}"
        assert "Files imported: 4" in result.output, f"Expected 4 files: {result.output}"

        # Verify all sources created
        from threadline.db.connection import Database
        from threadline.db.repositories.sources import SourceRepository

        db = Database(initialized_threadline / "threadline.db")
        source_repo = SourceRepository(db.conn)
        assert source_repo.count() == 4, "Expected 4 sources"
        db.close()


class TestStats:
    """Tests for `threadline stats` command."""

    def test_stats_returns_valid_counts(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """threadline stats returns valid counts matching database state."""
        # Ingest a file first
        runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        # Run stats
        result = runner.invoke(app, ["stats"])

        assert result.exit_code == 0, f"Stats failed: {result.output}"

        # Verify output contains expected sections
        assert "Sources (files)" in result.output
        assert "Entries" in result.output
        assert "Entries with embeddings" in result.output

        # Get actual counts from database
        from threadline.db.connection import Database
        from threadline.db.repositories.sources import SourceRepository
        from threadline.db.repositories.entries import EntryRepository

        db = Database(initialized_threadline / "threadline.db")
        source_repo = SourceRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        source_count = source_repo.count()
        entry_count = entry_repo.count()
        db.close()

        # Verify counts appear in output
        assert str(source_count) in result.output, "Source count not in output"
        assert str(entry_count) in result.output, "Entry count not in output"

    def test_stats_empty_database(self, initialized_threadline: Path) -> None:
        """threadline stats works on empty database."""
        result = runner.invoke(app, ["stats"])

        assert result.exit_code == 0, f"Stats failed: {result.output}"
        assert "Sources (files)" in result.output


class TestEntryHasEmbedding:
    """Tests for embedding generation."""

    @pytest.mark.slow
    def test_ingested_entries_have_embeddings(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Ingested entries have non-null embeddings."""
        # Ingest WITH embeddings (no --no-embeddings flag)
        result = runner.invoke(app, ["ingest", str(sample_markdown)])

        assert result.exit_code == 0, f"Ingest failed: {result.output}"

        # Verify embeddings were generated
        from threadline.db.connection import Database
        from threadline.db.repositories.entries import EntryRepository

        db = Database(initialized_threadline / "threadline.db")
        entry_repo = EntryRepository(db.conn)

        entries = entry_repo.list()
        assert len(entries) > 0, "No entries created"

        entries_with_embeddings = [e for e in entries if e.embedding is not None]
        assert len(entries_with_embeddings) == len(entries), (
            f"Not all entries have embeddings: {len(entries_with_embeddings)}/{len(entries)}"
        )

        # Verify embedding is the right size (384 dimensions * 4 bytes = 1536 bytes)
        for entry in entries:
            assert entry.embedding is not None
            assert len(entry.embedding) == 384 * 4, (
                f"Unexpected embedding size: {len(entry.embedding)}"
            )

        db.close()


class TestEntryHasClassification:
    """Tests for entry classification."""

    @pytest.mark.slow
    def test_ingested_entries_have_classification(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Ingested entries have entry_type and confidence."""
        # Ingest file
        result = runner.invoke(app, ["ingest", str(sample_markdown)])

        assert result.exit_code == 0, f"Ingest failed: {result.output}"

        # Verify classification was run
        from threadline.db.connection import Database
        from threadline.db.repositories.entries import EntryRepository

        db = Database(initialized_threadline / "threadline.db")
        entry_repo = EntryRepository(db.conn)

        entries = entry_repo.list()
        assert len(entries) > 0, "No entries created"

        entries_with_type = [e for e in entries if e.entry_type is not None]
        assert len(entries_with_type) == len(entries), (
            f"Not all entries have entry_type: {len(entries_with_type)}/{len(entries)}"
        )

        # Verify confidence scores exist
        for entry in entries:
            assert entry.entry_type is not None, f"Entry {entry.id} has no entry_type"
            assert entry.entry_type_confidence is not None, (
                f"Entry {entry.id} has no confidence score"
            )
            assert 0 <= entry.entry_type_confidence <= 1, (
                f"Entry {entry.id} has invalid confidence: {entry.entry_type_confidence}"
            )

        db.close()


class TestOCRImageDetection:
    """Tests for OCR image detection during ingestion."""

    def test_image_file_detected_during_scan(
        self, initialized_threadline: Path, sample_image: Path
    ) -> None:
        """Image files are detected during ingestion."""
        from threadline.ingest.file_scanner import scan_path

        scanned_files = list(scan_path(sample_image))
        assert len(scanned_files) == 1, "Image file not detected"
        assert scanned_files[0].file_type == "image", "File type should be 'image'"

    def test_image_ingest_graceful_failure_without_ocr(
        self, initialized_threadline: Path, sample_image: Path
    ) -> None:
        """Image ingestion fails gracefully when OCR dependencies not installed."""
        # Attempt to ingest image - should fail gracefully (pytesseract not installed)
        result = runner.invoke(app, ["ingest", str(sample_image), "--no-embeddings"])

        # Should complete without crashing
        assert result.exit_code == 0, f"Ingest crashed: {result.output}"

        # Should report failure or skip
        # Either files_failed=1 or files_skipped=1 depending on OCR availability
        assert "Files imported: 0" in result.output or "Files failed: 1" in result.output

    def test_ocr_flag_accepted(
        self, initialized_threadline: Path, sample_image: Path
    ) -> None:
        """The --ocr flag is accepted by the CLI."""
        # Test that the flag is recognized (even if OCR fails due to missing deps)
        result = runner.invoke(
            app, ["ingest", str(sample_image), "--no-embeddings", "--ocr=pytesseract"]
        )

        # Should not crash with unknown option error
        assert "No such option" not in result.output, "OCR flag not recognized"
