"""Repository for entries."""

from __future__ import annotations

import sqlite3
from datetime import datetime, date

from threadline.ingest.models import Entry, EntryCreate


class EntryRepository:
    """Data access for entries table."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, entry: EntryCreate) -> int:
        """Create a new entry, return its ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO entries (
                source_id, content, title, entry_date, location,
                entry_type, entry_type_confidence, summary_quote,
                embedding, source_line_start, source_line_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.source_id,
                entry.content,
                entry.title,
                entry.entry_date.isoformat() if entry.entry_date else None,
                entry.location,
                entry.entry_type,
                entry.entry_type_confidence,
                entry.summary_quote,
                entry.embedding,
                entry.source_line_start,
                entry.source_line_end,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def create_many(self, entries: list[EntryCreate]) -> list[int]:
        """Create multiple entries, return their IDs."""
        ids = []
        for entry in entries:
            ids.append(self.create(entry))
        return ids

    def get(self, entry_id: int) -> Entry | None:
        """Get an entry by ID."""
        row = self.conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()

        if row is None:
            return None

        entry = self._row_to_entry(row)
        entry.tags = self._get_tags(entry_id)
        return entry

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        entry_types: list[str] | None = None,
        tag_ids: list[int] | None = None,
        source_id: int | None = None,
    ) -> list[Entry]:
        """List entries with optional filters."""
        query = "SELECT DISTINCT e.* FROM entries e"
        params: list = []
        joins = []
        conditions = []

        # Join for tag filtering
        if tag_ids:
            joins.append("JOIN entry_tags et ON e.id = et.entry_id")
            placeholders = ",".join("?" * len(tag_ids))
            conditions.append(f"et.tag_id IN ({placeholders})")
            params.extend(tag_ids)

        # Filter by entry type
        if entry_types:
            placeholders = ",".join("?" * len(entry_types))
            conditions.append(f"e.entry_type IN ({placeholders})")
            params.extend(entry_types)

        # Filter by source
        if source_id is not None:
            conditions.append("e.source_id = ?")
            params.append(source_id)

        # Build query
        if joins:
            query += " " + " ".join(joins)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY e.entry_date DESC NULLS LAST, e.id DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
        entries = [self._row_to_entry(row) for row in rows]

        # Load tags for each entry
        for entry in entries:
            entry.tags = self._get_tags(entry.id)

        return entries

    def count(
        self,
        entry_types: list[str] | None = None,
        tag_ids: list[int] | None = None,
    ) -> int:
        """Count entries with optional filters."""
        query = "SELECT COUNT(DISTINCT e.id) FROM entries e"
        params: list = []
        joins = []
        conditions = []

        if tag_ids:
            joins.append("JOIN entry_tags et ON e.id = et.entry_id")
            placeholders = ",".join("?" * len(tag_ids))
            conditions.append(f"et.tag_id IN ({placeholders})")
            params.extend(tag_ids)

        if entry_types:
            placeholders = ",".join("?" * len(entry_types))
            conditions.append(f"e.entry_type IN ({placeholders})")
            params.extend(entry_types)

        if joins:
            query += " " + " ".join(joins)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        row = self.conn.execute(query, params).fetchone()
        return row[0]

    def update_embedding(self, entry_id: int, embedding: bytes) -> None:
        """Update an entry's embedding."""
        self.conn.execute(
            "UPDATE entries SET embedding = ? WHERE id = ?",
            (embedding, entry_id),
        )
        self.conn.commit()

    def update_classification(
        self, entry_id: int, entry_type: str, confidence: float
    ) -> None:
        """Update an entry's classification."""
        self.conn.execute(
            "UPDATE entries SET entry_type = ?, entry_type_confidence = ? WHERE id = ?",
            (entry_type, confidence, entry_id),
        )
        self.conn.commit()

    def get_entries_without_embeddings(self, limit: int = 100) -> list[Entry]:
        """Get entries that don't have embeddings yet."""
        rows = self.conn.execute(
            """
            SELECT * FROM entries
            WHERE embedding IS NULL
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def delete(self, entry_id: int) -> bool:
        """Delete an entry."""
        cursor = self.conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def _get_tags(self, entry_id: int) -> list[str]:
        """Get tag names for an entry."""
        rows = self.conn.execute(
            """
            SELECT t.name FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
            ORDER BY t.name
            """,
            (entry_id,),
        ).fetchall()
        return [row["name"] for row in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> Entry:
        """Convert a database row to an Entry object."""
        entry_date = None
        if row["entry_date"]:
            try:
                entry_date = date.fromisoformat(row["entry_date"])
            except ValueError:
                pass

        return Entry(
            id=row["id"],
            source_id=row["source_id"],
            content=row["content"],
            title=row["title"],
            entry_date=entry_date,
            location=row["location"],
            entry_type=row["entry_type"],
            entry_type_confidence=row["entry_type_confidence"],
            summary_quote=row["summary_quote"],
            embedding=row["embedding"],
            source_line_start=row["source_line_start"],
            source_line_end=row["source_line_end"],
            created_at=datetime.fromisoformat(row["created_at"]),
            tags=[],  # Populated separately
        )
