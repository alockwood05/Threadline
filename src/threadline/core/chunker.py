"""Text chunking for splitting documents into entries."""

from __future__ import annotations

import re
from threadline.ingest.models import Chunk


def chunk_text(
    text: str,
    min_chars: int = 30,
    preserve_lists: bool = True,
) -> list[Chunk]:
    """
    Split text into paragraph-based chunks.

    Args:
        text: The text to chunk
        min_chars: Minimum characters for a chunk (skip smaller ones)
        preserve_lists: If True, treat consecutive list items as one chunk

    Returns:
        List of Chunk objects with content and line positions
    """
    if not text.strip():
        return []

    lines = text.split("\n")
    chunks = []
    current_chunk_lines: list[str] = []
    current_chunk_start: int = 0
    in_list = False

    def flush_chunk():
        nonlocal current_chunk_lines, current_chunk_start, in_list
        if current_chunk_lines:
            content = "\n".join(current_chunk_lines).strip()
            if len(content) >= min_chars:
                chunks.append(
                    Chunk(
                        content=content,
                        line_start=current_chunk_start,
                        line_end=current_chunk_start + len(current_chunk_lines) - 1,
                    )
                )
        current_chunk_lines = []
        in_list = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this is a list item
        is_list_item = bool(
            re.match(r"^[-*+]\s", stripped)  # Unordered list
            or re.match(r"^\d+[.)]\s", stripped)  # Ordered list
            or re.match(r"^[-*+]\s*\[[ x]\]", stripped, re.IGNORECASE)  # Checkbox
        )

        # Empty line - potential chunk boundary
        if not stripped:
            if not in_list:
                flush_chunk()
            # Don't reset current_chunk_start yet - wait for next content
            continue

        # Start tracking position if this is first content line
        if not current_chunk_lines:
            current_chunk_start = i

        # Handle list items
        if preserve_lists and is_list_item:
            if not in_list and current_chunk_lines:
                # Starting a new list - flush previous content
                flush_chunk()
                current_chunk_start = i
            in_list = True
            current_chunk_lines.append(line)
        elif in_list and not is_list_item:
            # End of list
            flush_chunk()
            current_chunk_start = i
            current_chunk_lines.append(line)
        else:
            current_chunk_lines.append(line)

    # Flush remaining content
    flush_chunk()

    return chunks


def generate_summary_quote(content: str, max_length: int = 100) -> str:
    """
    Generate a summary quote for an entry.

    For short content, returns the full text.
    For longer content, returns the first sentence or truncated text.

    Args:
        content: The entry content
        max_length: Maximum length of the summary

    Returns:
        A summary string
    """
    content = content.strip()

    # Short content - use as is
    if len(content) <= max_length:
        # Collapse whitespace
        return " ".join(content.split())

    # Try to find first sentence
    # Look for sentence endings: . ! ?
    sentence_end = re.search(r"[.!?]\s", content[:max_length + 50])
    if sentence_end and sentence_end.end() <= max_length + 10:
        summary = content[: sentence_end.end()].strip()
        return " ".join(summary.split())

    # Truncate at word boundary
    truncated = content[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.7:  # Don't cut too much
        truncated = truncated[:last_space]

    return " ".join(truncated.split()) + "..."


def generate_title_from_content(
    content: str,
    entry_date: str | None = None,
    location: str | None = None,
    max_desc_length: int = 50,
) -> str:
    """
    Generate a title from entry content.

    Format: YYYY-MM-DD - <description> - <location>

    Args:
        content: The entry content
        entry_date: Optional date string (ISO format)
        location: Optional location string
        max_desc_length: Maximum length for description part

    Returns:
        Generated title string
    """
    parts = []

    # Add date
    if entry_date:
        parts.append(entry_date)

    # Generate description from first line/sentence
    first_line = content.strip().split("\n")[0].strip()

    # Remove markdown formatting
    first_line = re.sub(r"^#+\s*", "", first_line)  # Headers
    first_line = re.sub(r"^\s*[-*+]\s*(\[[ x]\])?\s*", "", first_line)  # List items
    first_line = re.sub(r"\*\*([^*]+)\*\*", r"\1", first_line)  # Bold
    first_line = re.sub(r"\*([^*]+)\*", r"\1", first_line)  # Italic
    first_line = re.sub(r"`([^`]+)`", r"\1", first_line)  # Code

    # Truncate description
    if len(first_line) > max_desc_length:
        first_line = first_line[: max_desc_length - 3].rsplit(" ", 1)[0] + "..."

    if first_line:
        parts.append(first_line)

    # Add location
    if location:
        parts.append(location)

    return " - ".join(parts) if parts else "Untitled"
