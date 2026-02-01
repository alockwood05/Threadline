"""Repository for source files."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from threadline.ingest.models import Source, SourceCreate


class SourceRepository:
    """Data access for sources table."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, source: SourceCreate) -> int:
        """Create a new source, return its ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO sources (filename, filepath, file_hash, file_type, raw_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source.filename,
                source.filepath,
                source.file_hash,
                source.file_type,
                source.raw_text,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def get(self, source_id: int) -> Source | None:
        """Get a source by ID."""
        row = self.conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_source(row)

    def get_by_hash(self, file_hash: str) -> Source | None:
        """Get a source by file hash."""
        row = self.conn.execute(
            "SELECT * FROM sources WHERE file_hash = ?", (file_hash,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_source(row)

    def exists_by_hash(self, file_hash: str) -> bool:
        """Check if a source with this hash already exists."""
        row = self.conn.execute(
            "SELECT 1 FROM sources WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row is not None

    def list(self, limit: int = 100, offset: int = 0) -> list[Source]:
        """List sources with pagination."""
        rows = self.conn.execute(
            """
            SELECT * FROM sources
            ORDER BY imported_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        return [self._row_to_source(row) for row in rows]

    def count(self) -> int:
        """Get total source count."""
        row = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()
        return row[0]

    def delete(self, source_id: int) -> bool:
        """Delete a source and its entries (cascade)."""
        cursor = self.conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        """Convert a database row to a Source object."""
        return Source(
            id=row["id"],
            filename=row["filename"],
            filepath=row["filepath"],
            file_hash=row["file_hash"],
            file_type=row["file_type"],
            raw_text=row["raw_text"],
            imported_at=datetime.fromisoformat(row["imported_at"]),
        )
