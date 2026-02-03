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


class TestTagRepository:
    """Tests for tag repository functionality."""

    def test_tag_create_and_list(self, initialized_threadline: Path) -> None:
        """Tags can be created and listed."""
        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)

        # Create a tag
        tag_id = tag_repo.create(TagCreate(name="important", color="red"))
        assert tag_id > 0, "Tag ID should be positive"

        # List tags
        tags = tag_repo.list()
        assert len(tags) == 1, "Expected 1 tag"
        assert tags[0].name == "important"
        assert tags[0].color == "red"

        db.close()

    def test_tag_get_by_name(self, initialized_threadline: Path) -> None:
        """Tags can be retrieved by name."""
        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)

        # Create a tag
        tag_repo.create(TagCreate(name="TestTag"))

        # Get by name (case-insensitive)
        tag = tag_repo.get_by_name("testtag")
        assert tag is not None, "Tag not found by name"
        assert tag.name == "TestTag"

        db.close()

    def test_add_tag_to_entry(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Tags can be added to entries."""
        # First ingest a file
        runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.db.repositories.entries import EntryRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        # Create a tag
        tag_id = tag_repo.create(TagCreate(name="mytag"))

        # Get an entry
        entries = entry_repo.list()
        assert len(entries) > 0, "No entries to tag"
        entry_id = entries[0].id

        # Add tag to entry
        tag_repo.add_tag_to_entry(entry_id, tag_id)

        # Verify entry now has the tag
        entry = entry_repo.get(entry_id)
        assert entry is not None
        assert "mytag" in entry.tags, f"Tag not found in entry tags: {entry.tags}"

        db.close()

    def test_remove_tag_from_entry(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Tags can be removed from entries."""
        runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.db.repositories.entries import EntryRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        # Create and add a tag
        tag_id = tag_repo.create(TagCreate(name="removeme"))
        entries = entry_repo.list()
        entry_id = entries[0].id
        tag_repo.add_tag_to_entry(entry_id, tag_id)

        # Verify tag is present
        entry = entry_repo.get(entry_id)
        assert "removeme" in entry.tags

        # Remove the tag
        tag_repo.remove_tag_from_entry(entry_id, tag_id)

        # Verify tag is gone
        entry = entry_repo.get(entry_id)
        assert "removeme" not in entry.tags, "Tag should have been removed"

        db.close()

    def test_entry_tag_indicator_in_tui_model(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Entries with tags have them populated in the model."""
        runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.db.repositories.entries import EntryRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        # Create tags and assign to entry
        tag1_id = tag_repo.create(TagCreate(name="tag1"))
        tag2_id = tag_repo.create(TagCreate(name="tag2"))

        entries = entry_repo.list()
        entry_id = entries[0].id
        tag_repo.add_tag_to_entry(entry_id, tag1_id)
        tag_repo.add_tag_to_entry(entry_id, tag2_id)

        # Re-fetch entry through list() which populates tags
        entries = entry_repo.list()
        tagged_entry = next(e for e in entries if e.id == entry_id)

        assert len(tagged_entry.tags) == 2, f"Expected 2 tags, got {len(tagged_entry.tags)}"
        assert "tag1" in tagged_entry.tags
        assert "tag2" in tagged_entry.tags

        db.close()


class TestTagsCLI:
    """Tests for `threadline tags` CLI commands."""

    def test_tags_list_empty(self, initialized_threadline: Path) -> None:
        """threadline tags list shows message when no tags exist."""
        result = runner.invoke(app, ["tags", "list"])

        assert result.exit_code == 0, f"Tags list failed: {result.output}"
        assert "No tags found" in result.output

    def test_tags_create(self, initialized_threadline: Path) -> None:
        """threadline tags create creates a new tag."""
        result = runner.invoke(app, ["tags", "create", "important", "--color", "red"])

        assert result.exit_code == 0, f"Tags create failed: {result.output}"
        assert "Created tag 'important'" in result.output

        # Verify tag exists
        list_result = runner.invoke(app, ["tags", "list"])
        assert "important" in list_result.output
        assert "red" in list_result.output

    def test_tags_create_duplicate_fails(self, initialized_threadline: Path) -> None:
        """Creating duplicate tag fails with error."""
        runner.invoke(app, ["tags", "create", "duplicate"])
        result = runner.invoke(app, ["tags", "create", "duplicate"])

        assert result.exit_code == 1, "Should fail for duplicate tag"
        assert "already exists" in result.output

    def test_tags_delete(self, initialized_threadline: Path) -> None:
        """threadline tags delete removes a tag."""
        # Create a tag first
        runner.invoke(app, ["tags", "create", "todelete"])

        # Delete with --yes to skip confirmation
        result = runner.invoke(app, ["tags", "delete", "todelete", "--yes"])

        assert result.exit_code == 0, f"Tags delete failed: {result.output}"
        assert "Deleted tag 'todelete'" in result.output

        # Verify tag is gone
        list_result = runner.invoke(app, ["tags", "list"])
        assert "todelete" not in list_result.output

    def test_tags_delete_nonexistent_fails(self, initialized_threadline: Path) -> None:
        """Deleting non-existent tag fails."""
        result = runner.invoke(app, ["tags", "delete", "nonexistent", "--yes"])

        assert result.exit_code == 1, "Should fail for non-existent tag"
        assert "not found" in result.output

    def test_tags_rename(self, initialized_threadline: Path) -> None:
        """threadline tags rename changes tag name."""
        # Create a tag
        runner.invoke(app, ["tags", "create", "oldname"])

        # Rename it
        result = runner.invoke(app, ["tags", "rename", "oldname", "newname"])

        assert result.exit_code == 0, f"Tags rename failed: {result.output}"
        assert "Renamed tag 'oldname' to 'newname'" in result.output

        # Verify rename worked
        list_result = runner.invoke(app, ["tags", "list"])
        assert "newname" in list_result.output
        assert "oldname" not in list_result.output

    def test_tags_rename_to_existing_fails(self, initialized_threadline: Path) -> None:
        """Renaming to existing tag name fails."""
        runner.invoke(app, ["tags", "create", "tag1"])
        runner.invoke(app, ["tags", "create", "tag2"])

        result = runner.invoke(app, ["tags", "rename", "tag1", "tag2"])

        assert result.exit_code == 1, "Should fail when target name exists"
        assert "already exists" in result.output

    def test_tags_merge(self, initialized_threadline: Path) -> None:
        """threadline tags merge combines two tags."""
        # Create two tags
        runner.invoke(app, ["tags", "create", "source"])
        runner.invoke(app, ["tags", "create", "target"])

        # Merge with --yes
        result = runner.invoke(app, ["tags", "merge", "source", "target", "--yes"])

        assert result.exit_code == 0, f"Tags merge failed: {result.output}"
        assert "Merged 'source' into 'target'" in result.output

        # Verify source is gone, target remains
        list_result = runner.invoke(app, ["tags", "list"])
        assert "target" in list_result.output
        assert "source" not in list_result.output

    def test_tags_merge_moves_entries(
        self, initialized_threadline: Path, sample_markdown: Path
    ) -> None:
        """Tags merge moves entries from source to target tag."""
        # Ingest a file to create entries
        runner.invoke(app, ["ingest", str(sample_markdown), "--no-embeddings"])

        from threadline.db.connection import Database
        from threadline.db.repositories.tags import TagRepository
        from threadline.db.repositories.entries import EntryRepository
        from threadline.ingest.models import TagCreate

        db = Database(initialized_threadline / "threadline.db")
        tag_repo = TagRepository(db.conn)
        entry_repo = EntryRepository(db.conn)

        # Create tags via CLI
        runner.invoke(app, ["tags", "create", "fromtag"])
        runner.invoke(app, ["tags", "create", "totag"])

        # Get tag IDs
        fromtag = tag_repo.get_by_name("fromtag")
        totag = tag_repo.get_by_name("totag")

        # Add fromtag to an entry
        entries = entry_repo.list()
        entry_id = entries[0].id
        tag_repo.add_tag_to_entry(entry_id, fromtag.id)

        db.close()

        # Merge via CLI
        result = runner.invoke(app, ["tags", "merge", "fromtag", "totag", "--yes"])
        assert result.exit_code == 0

        # Verify entry now has totag
        db = Database(initialized_threadline / "threadline.db")
        entry_repo = EntryRepository(db.conn)
        entry = entry_repo.get(entry_id)

        assert "totag" in entry.tags, f"Entry should have totag: {entry.tags}"
        assert "fromtag" not in entry.tags, "Entry should not have fromtag"

        db.close()
