"""Repository for themes and entry-theme relationships."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from threadline.ingest.models import Theme, ThemeCreate


class ThemeRepository:
    """Data access for themes and entry_themes tables."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, theme: ThemeCreate) -> int:
        """Create a new theme, return its ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO themes (topic_id, name, keywords, representative_docs, entry_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                theme.topic_id,
                theme.name,
                theme.keywords,
                theme.representative_docs,
                theme.entry_count,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def get(self, theme_id: int) -> Theme | None:
        """Get a theme by ID."""
        row = self.conn.execute(
            "SELECT * FROM themes WHERE id = ?", (theme_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_theme(row)

    def get_by_topic_id(self, topic_id: int) -> Theme | None:
        """Get a theme by BERTopic's topic_id."""
        row = self.conn.execute(
            "SELECT * FROM themes WHERE topic_id = ?", (topic_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_theme(row)

    def list(self, limit: int = 100, offset: int = 0) -> list[Theme]:
        """List all themes ordered by entry count (most entries first)."""
        rows = self.conn.execute(
            """
            SELECT * FROM themes
            ORDER BY entry_count DESC, name ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [self._row_to_theme(row) for row in rows]

    def count(self) -> int:
        """Count total themes."""
        row = self.conn.execute("SELECT COUNT(*) FROM themes").fetchone()
        return row[0]

    def delete(self, theme_id: int) -> bool:
        """Delete a theme (also removes from entry_themes via CASCADE)."""
        cursor = self.conn.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Delete all themes and entry_theme relationships. Used before re-extraction."""
        self.conn.execute("DELETE FROM entry_themes")
        self.conn.execute("DELETE FROM themes")
        self.conn.commit()

    def add_entry_to_theme(self, entry_id: int, theme_id: int, probability: float) -> None:
        """Add an entry to a theme with probability score."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO entry_themes (entry_id, theme_id, probability)
            VALUES (?, ?, ?)
            """,
            (entry_id, theme_id, probability),
        )
        self.conn.commit()

    def add_entries_to_theme_batch(
        self, entries: list[tuple[int, int, float]]
    ) -> None:
        """Batch add entries to themes. entries: list of (entry_id, theme_id, probability)."""
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO entry_themes (entry_id, theme_id, probability)
            VALUES (?, ?, ?)
            """,
            entries,
        )
        self.conn.commit()

    def get_entries_by_theme(self, theme_id: int, limit: int = 50, offset: int = 0) -> list[int]:
        """Get entry IDs for a theme, ordered by probability (highest first)."""
        rows = self.conn.execute(
            """
            SELECT entry_id FROM entry_themes
            WHERE theme_id = ?
            ORDER BY probability DESC
            LIMIT ? OFFSET ?
            """,
            (theme_id, limit, offset),
        ).fetchall()
        return [row["entry_id"] for row in rows]

    def get_theme_for_entry(self, entry_id: int) -> tuple[int, float] | None:
        """Get the primary theme ID and probability for an entry (highest probability)."""
        row = self.conn.execute(
            """
            SELECT theme_id, probability FROM entry_themes
            WHERE entry_id = ?
            ORDER BY probability DESC
            LIMIT 1
            """,
            (entry_id,),
        ).fetchone()

        if row is None:
            return None

        return row["theme_id"], row["probability"]

    def update_entry_count(self, theme_id: int, count: int) -> None:
        """Update the entry_count for a theme."""
        self.conn.execute(
            "UPDATE themes SET entry_count = ? WHERE id = ?",
            (count, theme_id),
        )
        self.conn.commit()

    def record_model_run(
        self, model_name: str, model_version: str | None, entries_processed: int
    ) -> int:
        """Record a theme extraction run in model_runs table."""
        cursor = self.conn.execute(
            """
            INSERT INTO model_runs (run_type, model_name, model_version, entries_processed)
            VALUES ('themes', ?, ?, ?)
            """,
            (model_name, model_version, entries_processed),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def _row_to_theme(self, row: sqlite3.Row) -> Theme:
        """Convert a database row to a Theme object."""
        return Theme(
            id=row["id"],
            topic_id=row["topic_id"],
            name=row["name"],
            keywords=row["keywords"],
            representative_docs=row["representative_docs"],
            entry_count=row["entry_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
