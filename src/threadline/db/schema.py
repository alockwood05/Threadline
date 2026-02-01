"""Database schema definitions."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- Sources: original imported files
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL CHECK (file_type IN ('markdown', 'image')),
    raw_text TEXT,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(file_hash);

-- Entries: individual thought-units
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    title TEXT,
    entry_date TEXT,
    location TEXT,
    entry_type TEXT,
    entry_type_confidence REAL,
    summary_quote TEXT,
    embedding BLOB,
    source_line_start INTEGER,
    source_line_end INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source_id);
CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(entry_type);

-- Tags: user-defined labels
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Entry-Tag junction
CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON entry_tags(tag_id);

-- Themes: auto-extracted topics
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    keywords TEXT,
    representative_docs TEXT,
    entry_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Entry-Theme junction
CREATE TABLE IF NOT EXISTS entry_themes (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    probability REAL,
    PRIMARY KEY (entry_id, theme_id)
);

CREATE INDEX IF NOT EXISTS idx_entry_themes_theme ON entry_themes(theme_id);

-- Model runs: track processing history
CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL CHECK (run_type IN ('embedding', 'classification', 'themes')),
    model_name TEXT NOT NULL,
    model_version TEXT,
    entries_processed INTEGER,
    run_at TEXT DEFAULT (datetime('now'))
);
"""


def get_schema_sql() -> str:
    """Get the full schema SQL."""
    return SCHEMA_SQL


def get_vss_setup_sql(dimensions: int = 384) -> str:
    """Get SQL to set up sqlite-vss virtual table."""
    return f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS entries_vss USING vss0(embedding({dimensions}));
    """
