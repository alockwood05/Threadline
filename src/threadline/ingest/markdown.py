"""Markdown parsing with frontmatter support."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re

import frontmatter
import dateparser

from threadline.ingest.models import ParsedDocument


def parse_markdown_file(path: Path) -> ParsedDocument:
    """
    Parse a markdown file, extracting frontmatter and content.

    Args:
        path: Path to the markdown file

    Returns:
        ParsedDocument with raw text and extracted metadata
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    return parse_markdown_content(content, filename=path.name)


def parse_markdown_content(content: str, filename: str | None = None) -> ParsedDocument:
    """
    Parse markdown content, extracting frontmatter and content.

    Args:
        content: Raw markdown content
        filename: Optional filename for date extraction fallback

    Returns:
        ParsedDocument with raw text and extracted metadata
    """
    # Parse frontmatter
    post = frontmatter.loads(content)
    fm = dict(post.metadata)
    raw_text = post.content

    # Extract date from frontmatter or content
    entry_date = None

    # Try frontmatter first
    if "date" in fm:
        entry_date = _parse_date(fm["date"])
    elif "created" in fm:
        entry_date = _parse_date(fm["created"])

    # Try to extract from content
    if entry_date is None:
        entry_date = _extract_date_from_content(raw_text)

    # Try filename as last resort
    if entry_date is None and filename:
        entry_date = _extract_date_from_filename(filename)

    # Extract title from frontmatter
    title = fm.get("title")

    # Extract location from frontmatter
    location = fm.get("location")

    return ParsedDocument(
        raw_text=raw_text,
        title=title,
        date=entry_date,
        location=location,
        frontmatter=fm,
    )


def _parse_date(value) -> date | None:
    """Parse a date value that might be string, date, or datetime."""
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if hasattr(value, "date"):  # datetime
        return value.date()

    if isinstance(value, str):
        parsed = dateparser.parse(value)
        if parsed:
            return parsed.date()

    return None


def _extract_date_from_content(content: str) -> date | None:
    """Try to extract a date from the first few lines of content."""
    # Look in first 500 chars
    head = content[:500]

    # Common date patterns at start of journal entries
    patterns = [
        # 2024-01-15
        r"\b(\d{4}-\d{2}-\d{2})\b",
        # January 15, 2024
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
        # 15 January 2024
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
        # Jan 15, 2024
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b",
        # 1/15/2024 or 01/15/2024
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, head, re.IGNORECASE)
        if match:
            parsed = dateparser.parse(match.group(1))
            if parsed:
                return parsed.date()

    return None


def _extract_date_from_filename(filename: str) -> date | None:
    """Try to extract a date from a filename."""
    # Common filename patterns
    patterns = [
        # 2024-01-15-title.md or 2024-01-15_title.md
        r"^(\d{4}-\d{2}-\d{2})",
        # 20240115-title.md
        r"^(\d{8})",
        # journal_2024-01-15.md
        r"(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            parsed = dateparser.parse(match.group(1))
            if parsed:
                return parsed.date()

    return None
