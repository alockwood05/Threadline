"""CLI stats command."""

import typer
from rich.console import Console
from rich.table import Table

from threadline.config.paths import get_db_path, get_originals_dir
from threadline.db.connection import Database
from threadline.db.repositories.sources import SourceRepository
from threadline.db.repositories.entries import EntryRepository

console = Console()


def stats_cmd() -> None:
    """Show database statistics."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    source_repo = SourceRepository(db.conn)
    entry_repo = EntryRepository(db.conn)

    # Gather stats
    source_count = source_repo.count()
    entry_count = entry_repo.count()

    # Count entries by type
    type_counts = db.conn.execute(
        """
        SELECT entry_type, COUNT(*) as count
        FROM entries
        GROUP BY entry_type
        ORDER BY count DESC
        """
    ).fetchall()

    # Count entries with embeddings
    embedding_count = db.conn.execute(
        "SELECT COUNT(*) FROM entries WHERE embedding IS NOT NULL"
    ).fetchone()[0]

    # Get originals directory size
    originals_dir = get_originals_dir()
    originals_size = sum(f.stat().st_size for f in originals_dir.rglob("*") if f.is_file())
    originals_size_mb = originals_size / (1024 * 1024)

    # Database size
    db_size = db_path.stat().st_size / (1024 * 1024)

    db.close()

    # Display
    console.print()
    table = Table(title="Threadline Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Sources (files)", str(source_count))
    table.add_row("Entries", str(entry_count))
    table.add_row("Entries with embeddings", f"{embedding_count} ({embedding_count/max(entry_count,1)*100:.0f}%)")
    table.add_row("Database size", f"{db_size:.2f} MB")
    table.add_row("Originals size", f"{originals_size_mb:.2f} MB")

    console.print(table)

    if type_counts:
        console.print()
        type_table = Table(title="Entries by Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="green")

        for row in type_counts:
            entry_type = row["entry_type"] or "(unclassified)"
            type_table.add_row(entry_type, str(row["count"]))

        console.print(type_table)
