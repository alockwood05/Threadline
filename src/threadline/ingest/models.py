"""Data models for ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class SourceCreate:
    """Data for creating a new source."""

    filename: str
    filepath: str
    file_hash: str
    file_type: str  # 'markdown' or 'image'
    raw_text: str | None = None


@dataclass
class Source:
    """A source file record."""

    id: int
    filename: str
    filepath: str
    file_hash: str
    file_type: str
    raw_text: str | None
    imported_at: datetime


@dataclass
class Chunk:
    """A chunk of text with position information."""

    content: str
    line_start: int
    line_end: int


@dataclass
class EntryCreate:
    """Data for creating a new entry."""

    source_id: int
    content: str
    title: str | None = None
    entry_date: date | None = None
    location: str | None = None
    entry_type: str | None = None
    entry_type_confidence: float | None = None
    summary_quote: str | None = None
    embedding: bytes | None = None
    source_line_start: int | None = None
    source_line_end: int | None = None


@dataclass
class Entry:
    """An entry record."""

    id: int
    source_id: int
    content: str
    title: str | None
    entry_date: date | None
    location: str | None
    entry_type: str | None
    entry_type_confidence: float | None
    summary_quote: str | None
    embedding: bytes | None
    source_line_start: int | None
    source_line_end: int | None
    created_at: datetime
    tags: list[str] = field(default_factory=list)


@dataclass
class ScannedFile:
    """A file found during scanning."""

    path: Path
    filename: str
    file_hash: str
    file_type: str  # 'markdown' or 'image'


@dataclass
class ParsedDocument:
    """A parsed document with metadata."""

    raw_text: str
    title: str | None = None
    date: date | None = None
    location: str | None = None
    frontmatter: dict = field(default_factory=dict)


@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    files_imported: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    entries_created: int = 0
    errors: list[str] = field(default_factory=list)
