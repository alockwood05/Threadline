"""Database connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from threadline.db.schema import get_schema_sql, get_vss_setup_sql, SCHEMA_VERSION


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._vss_available: bool = False

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = self._create_connection()
        return self._conn

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _try_load_vss(self) -> bool:
        """Attempt to load sqlite-vss extension."""
        try:
            import sqlite_vss

            self.conn.enable_load_extension(True)
            sqlite_vss.load(self.conn)
            self._vss_available = True
            return True
        except (ImportError, Exception):
            self._vss_available = False
            return False

    def init_schema(self, embedding_dimensions: int = 384) -> None:
        """Initialize database schema."""
        # Create base tables
        self.conn.executescript(get_schema_sql())

        # Record schema version
        self.conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

        # Try to set up vector search
        if self._try_load_vss():
            try:
                self.conn.executescript(get_vss_setup_sql(embedding_dimensions))
            except sqlite3.OperationalError:
                # VSS table might already exist
                pass

        self.conn.commit()

    @property
    def vss_available(self) -> bool:
        """Check if sqlite-vss is available."""
        return self._vss_available

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


@contextmanager
def get_db(db_path: Path | None = None) -> Generator[Database, None, None]:
    """Context manager for database access."""
    if db_path is None:
        from threadline.config.paths import get_db_path

        db_path = get_db_path()

    db = Database(db_path)
    try:
        yield db
    finally:
        db.close()


def init_database(db_path: Path | None = None, embedding_dimensions: int = 384) -> Database:
    """Initialize a new database with schema."""
    if db_path is None:
        from threadline.config.paths import get_db_path

        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.init_schema(embedding_dimensions)
    return db
