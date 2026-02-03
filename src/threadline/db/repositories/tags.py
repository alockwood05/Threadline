"""Repository for tags."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from threadline.ingest.models import Tag, TagCreate


class TagRepository:
    """Data access for tags table."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, tag: TagCreate) -> int:
        """Create a new tag, return its ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO tags (name, color)
            VALUES (?, ?)
            """,
            (tag.name, tag.color),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore

    def get(self, tag_id: int) -> Tag | None:
        """Get a tag by ID."""
        row = self.conn.execute(
            "SELECT * FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_tag(row)

    def get_by_name(self, name: str) -> Tag | None:
        """Get a tag by name (case-insensitive)."""
        row = self.conn.execute(
            "SELECT * FROM tags WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()

        if row is None:
            return None

        return self._row_to_tag(row)

    def list(self) -> list[Tag]:
        """List all tags ordered by name."""
        rows = self.conn.execute(
            "SELECT * FROM tags ORDER BY name"
        ).fetchall()
        return [self._row_to_tag(row) for row in rows]

    def delete(self, tag_id: int) -> bool:
        """Delete a tag (also removes from entry_tags via CASCADE)."""
        cursor = self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def rename(self, tag_id: int, new_name: str) -> bool:
        """Rename a tag."""
        cursor = self.conn.execute(
            "UPDATE tags SET name = ? WHERE id = ?",
            (new_name, tag_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def merge(self, source_id: int, target_id: int) -> int:
        """Merge source tag into target tag.

        Moves all entries from source tag to target tag (ignoring duplicates),
        then deletes the source tag.

        Returns the number of entries moved.
        """
        # Get entries that have the source tag but not the target tag
        # (we don't want to create duplicate entry_tags)
        cursor = self.conn.execute(
            """
            UPDATE entry_tags
            SET tag_id = ?
            WHERE tag_id = ?
            AND entry_id NOT IN (
                SELECT entry_id FROM entry_tags WHERE tag_id = ?
            )
            """,
            (target_id, source_id, target_id),
        )
        moved_count = cursor.rowcount

        # Delete the source tag (CASCADE will remove any remaining entry_tags)
        self.conn.execute("DELETE FROM tags WHERE id = ?", (source_id,))
        self.conn.commit()

        return moved_count

    def get_entry_tag_ids(self, entry_id: int) -> list[int]:
        """Get tag IDs for an entry."""
        rows = self.conn.execute(
            "SELECT tag_id FROM entry_tags WHERE entry_id = ?",
            (entry_id,),
        ).fetchall()
        return [row["tag_id"] for row in rows]

    def add_tag_to_entry(self, entry_id: int, tag_id: int) -> None:
        """Add a tag to an entry (idempotent)."""
        self.conn.execute(
            """
            INSERT OR IGNORE INTO entry_tags (entry_id, tag_id)
            VALUES (?, ?)
            """,
            (entry_id, tag_id),
        )
        self.conn.commit()

    def remove_tag_from_entry(self, entry_id: int, tag_id: int) -> None:
        """Remove a tag from an entry."""
        self.conn.execute(
            "DELETE FROM entry_tags WHERE entry_id = ? AND tag_id = ?",
            (entry_id, tag_id),
        )
        self.conn.commit()

    def set_entry_tags(self, entry_id: int, tag_ids: list[int]) -> None:
        """Replace all tags for an entry with the given tag IDs."""
        self.conn.execute(
            "DELETE FROM entry_tags WHERE entry_id = ?",
            (entry_id,),
        )
        for tag_id in tag_ids:
            self.conn.execute(
                "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                (entry_id, tag_id),
            )
        self.conn.commit()

    def _row_to_tag(self, row: sqlite3.Row) -> Tag:
        """Convert a database row to a Tag object."""
        return Tag(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
