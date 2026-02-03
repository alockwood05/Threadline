"""CLI command for exporting entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from threadline.db.connection import get_db
from threadline.db.repositories.entries import EntryRepository
from threadline.db.repositories.tags import TagRepository
from threadline.db.repositories.sources import SourceRepository

console = Console()


def _format_entry_markdown(entry, source_path: str | None = None) -> str:
    """Format a single entry as markdown."""
    lines = []

    # Header with title
    title = entry.title or "Untitled"
    lines.append(f"## {title}")
    lines.append("")

    # Metadata block
    metadata = []
    if entry.entry_date:
        metadata.append(f"**Date:** {entry.entry_date.isoformat()}")
    if entry.entry_type:
        confidence = ""
        if entry.entry_type_confidence:
            confidence = f" ({entry.entry_type_confidence:.0%})"
        metadata.append(f"**Type:** {entry.entry_type}{confidence}")
    if entry.location:
        metadata.append(f"**Location:** {entry.location}")
    if entry.tags:
        metadata.append(f"**Tags:** {', '.join(entry.tags)}")
    if source_path:
        metadata.append(f"**Source:** {source_path}")

    if metadata:
        lines.extend(metadata)
        lines.append("")

    # Content
    lines.append(entry.content)
    lines.append("")

    return "\n".join(lines)


def _format_entry_json(entry, source_path: str | None = None) -> dict:
    """Format a single entry as a JSON-serializable dict."""
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "entry_type": entry.entry_type,
        "entry_type_confidence": entry.entry_type_confidence,
        "location": entry.location,
        "tags": entry.tags,
        "source": source_path,
        "summary_quote": entry.summary_quote,
    }


def export_cmd(
    output: Path = typer.Option(
        ...,
        "-o",
        "--output",
        help="Output file path",
    ),
    filter_type: Optional[list[str]] = typer.Option(
        None,
        "--filter-type",
        help="Filter by entry type (can be repeated for multiple types)",
    ),
    tag: Optional[list[str]] = typer.Option(
        None,
        "--tag",
        help="Filter by tag name (can be repeated for multiple tags)",
    ),
    format: str = typer.Option(
        "md",
        "--format",
        "-f",
        help="Output format: 'md' for markdown, 'json' for JSON",
    ),
    include_similar: bool = typer.Option(
        False,
        "--include-similar",
        help="Include similar entries for each matched entry",
    ),
    similar_limit: int = typer.Option(
        3,
        "--similar-limit",
        help="Number of similar entries to include per entry (with --include-similar)",
    ),
) -> None:
    """
    Export entries matching filters to markdown or JSON.

    Examples:
        threadline export -o output.md --filter-type=thought
        threadline export -o output.json --format=json --tag=important
        threadline export -o output.md --filter-type=reflection --include-similar
    """
    # Validate format
    if format not in ("md", "json"):
        console.print(f"[red]Error:[/red] Invalid format '{format}'. Use 'md' or 'json'.")
        raise typer.Exit(1)

    with get_db() as db:
        entry_repo = EntryRepository(db.conn)
        tag_repo = TagRepository(db.conn)
        source_repo = SourceRepository(db.conn)

        # Convert tag names to tag IDs
        tag_ids = None
        if tag:
            tag_ids = []
            for tag_name in tag:
                tag_obj = tag_repo.get_by_name(tag_name)
                if tag_obj:
                    tag_ids.append(tag_obj.id)
                else:
                    console.print(f"[yellow]Warning:[/yellow] Tag '{tag_name}' not found, ignoring")

            # If all tags were invalid, set to None to avoid empty filter
            if not tag_ids:
                tag_ids = None

        # Get matching entries
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching entries...", total=None)

            # Use a high limit to get all matching entries
            entries = entry_repo.list(
                limit=100000,
                offset=0,
                entry_types=filter_type,
                tag_ids=tag_ids,
            )

        if not entries:
            console.print("[yellow]No entries match the specified filters.[/yellow]")
            raise typer.Exit(0)

        # Build source path cache
        source_cache: dict[int, str] = {}

        def get_source_path(source_id: int) -> str | None:
            if source_id not in source_cache:
                source = source_repo.get(source_id)
                source_cache[source_id] = source.filepath if source else None
            return source_cache[source_id]

        # Track entries to export (may include similar entries)
        entries_to_export = list(entries)
        similar_groups: dict[int, list[tuple]] = {}  # entry_id -> list of (similar_entry, score)

        if include_similar:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Finding similar entries...", total=len(entries))

                seen_ids = {e.id for e in entries}

                for entry in entries:
                    if entry.embedding:
                        similar_results = entry_repo.find_similar(entry.id, limit=similar_limit)
                        similar_groups[entry.id] = similar_results

                        # Add similar entries to export list if not already included
                        for similar_entry, _ in similar_results:
                            if similar_entry.id not in seen_ids:
                                entries_to_export.append(similar_entry)
                                seen_ids.add(similar_entry.id)

                    progress.advance(task)

        # Export based on format
        if format == "md":
            lines = [
                "# Threadline Export",
                "",
                f"**Total entries:** {len(entries)}",
            ]

            if filter_type:
                lines.append(f"**Filter types:** {', '.join(filter_type)}")
            if tag:
                lines.append(f"**Filter tags:** {', '.join(tag)}")
            if include_similar:
                unique_similar = len(entries_to_export) - len(entries)
                lines.append(f"**Similar entries included:** {unique_similar}")

            lines.extend(["", "---", ""])

            for entry in entries:
                source_path = get_source_path(entry.source_id)
                lines.append(_format_entry_markdown(entry, source_path))

                # Add similar entries if requested
                if include_similar and entry.id in similar_groups:
                    similar = similar_groups[entry.id]
                    if similar:
                        lines.append("### Similar Entries")
                        lines.append("")
                        for similar_entry, score in similar:
                            similar_source = get_source_path(similar_entry.source_id)
                            lines.append(f"*Similarity: {score:.1%}*")
                            lines.append("")
                            lines.append(_format_entry_markdown(similar_entry, similar_source))

                lines.append("---")
                lines.append("")

            output_content = "\n".join(lines)

        else:  # JSON format
            export_data = {
                "metadata": {
                    "total_entries": len(entries),
                    "filter_types": filter_type,
                    "filter_tags": tag,
                    "include_similar": include_similar,
                },
                "entries": [],
            }

            for entry in entries:
                source_path = get_source_path(entry.source_id)
                entry_data = _format_entry_json(entry, source_path)

                if include_similar and entry.id in similar_groups:
                    entry_data["similar_entries"] = [
                        {
                            "similarity": score,
                            **_format_entry_json(similar_entry, get_source_path(similar_entry.source_id))
                        }
                        for similar_entry, score in similar_groups[entry.id]
                    ]

                export_data["entries"].append(entry_data)

            output_content = json.dumps(export_data, indent=2)

        # Write to file
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_content)

        console.print(f"\n[green]✓[/green] Exported {len(entries)} entries to {output}")
        if include_similar:
            unique_similar = len(entries_to_export) - len(entries)
            console.print(f"  (plus {unique_similar} similar entries)")
