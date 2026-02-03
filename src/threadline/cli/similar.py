"""CLI command for similarity search."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from threadline.db.connection import get_db
from threadline.db.repositories.entries import EntryRepository

console = Console()


def similar_cmd(entry_id: int) -> None:
    """
    Find similar entries using cosine similarity.

    Args:
        entry_id: The entry ID to find similar entries for
    """
    with get_db() as db:
        repo = EntryRepository(db.conn)

        # Get the reference entry
        reference = repo.get(entry_id)
        if not reference:
            console.print(f"[red]Error:[/red] Entry {entry_id} not found")
            raise typer.Exit(1)

        if not reference.embedding:
            console.print(
                f"[red]Error:[/red] Entry {entry_id} has no embedding. "
                "Run ingestion with embeddings enabled."
            )
            raise typer.Exit(1)

        # Find similar entries
        console.print(f"\n[bold]Finding entries similar to:[/bold] {reference.title or 'Untitled'}\n")

        similar_entries = repo.find_similar(entry_id, limit=10)

        if not similar_entries:
            console.print("[yellow]No similar entries found.[/yellow]")
            return

        # Create results table
        table = Table(title="Similar Entries", show_header=True)
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Similarity", style="green", width=10)
        table.add_column("Title", style="bold")
        table.add_column("Type", style="magenta", width=15)

        for entry, similarity in similar_entries:
            similarity_pct = f"{similarity * 100:.1f}%"
            title = entry.title or "Untitled"
            entry_type = entry.entry_type or "unknown"

            table.add_row(
                str(entry.id),
                similarity_pct,
                title[:50] + "..." if len(title) > 50 else title,
                entry_type,
            )

        console.print(table)
        console.print(
            f"\n[dim]Tip: Use 'threadline browse' to view entries in detail[/dim]\n"
        )
