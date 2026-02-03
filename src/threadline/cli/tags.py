"""CLI commands for tag management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from threadline.config.paths import get_db_path
from threadline.db.connection import Database
from threadline.db.repositories.tags import TagRepository
from threadline.ingest.models import TagCreate

app = typer.Typer(name="tags", help="Manage tags")
console = Console()


def _get_tag_counts(db: Database) -> dict[int, int]:
    """Get entry counts for each tag."""
    rows = db.conn.execute(
        """
        SELECT tag_id, COUNT(*) as count
        FROM entry_tags
        GROUP BY tag_id
        """
    ).fetchall()
    return {row["tag_id"]: row["count"] for row in rows}


@app.command(name="list")
def list_cmd() -> None:
    """Show all tags with entry counts."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    tag_repo = TagRepository(db.conn)

    tags = tag_repo.list()
    tag_counts = _get_tag_counts(db)

    db.close()

    if not tags:
        console.print("[yellow]No tags found.[/yellow]")
        return

    table = Table(title="Tags")
    table.add_column("Name", style="cyan")
    table.add_column("Entries", style="green", justify="right")
    table.add_column("Color", style="magenta")
    table.add_column("Created", style="dim")

    for tag in tags:
        count = tag_counts.get(tag.id, 0)
        color = tag.color or "-"
        created = tag.created_at.strftime("%Y-%m-%d")
        table.add_row(tag.name, str(count), color, created)

    console.print(table)
    console.print(f"\n[dim]Total: {len(tags)} tag(s)[/dim]")


@app.command(name="create")
def create_cmd(
    name: str = typer.Argument(..., help="Name for the new tag"),
    color: str = typer.Option(None, "--color", "-c", help="Color for the tag (e.g., 'red', '#ff0000')"),
) -> None:
    """Create a new tag."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    tag_repo = TagRepository(db.conn)

    # Check if tag already exists
    existing = tag_repo.get_by_name(name)
    if existing:
        console.print(f"[red]Tag '{name}' already exists.[/red]")
        db.close()
        raise typer.Exit(1)

    # Create the tag
    tag_create = TagCreate(name=name, color=color)
    tag_id = tag_repo.create(tag_create)

    db.close()

    console.print(f"[green]Created tag '{name}' (id={tag_id})[/green]")


@app.command(name="delete")
def delete_cmd(
    name: str = typer.Argument(..., help="Name of the tag to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete a tag (with confirmation)."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    tag_repo = TagRepository(db.conn)

    # Find the tag
    tag = tag_repo.get_by_name(name)
    if not tag:
        console.print(f"[red]Tag '{name}' not found.[/red]")
        db.close()
        raise typer.Exit(1)

    # Get entry count for this tag
    tag_counts = _get_tag_counts(db)
    entry_count = tag_counts.get(tag.id, 0)

    # Confirm deletion
    if not yes:
        if entry_count > 0:
            console.print(f"[yellow]Tag '{name}' is used by {entry_count} entries.[/yellow]")

        confirm = typer.confirm(f"Delete tag '{name}'?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            db.close()
            raise typer.Exit(0)

    # Delete the tag
    tag_repo.delete(tag.id)
    db.close()

    console.print(f"[green]Deleted tag '{name}'[/green]")
    if entry_count > 0:
        console.print(f"[dim]Removed from {entry_count} entries.[/dim]")


@app.command(name="rename")
def rename_cmd(
    old_name: str = typer.Argument(..., help="Current tag name"),
    new_name: str = typer.Argument(..., help="New tag name"),
) -> None:
    """Rename a tag."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    tag_repo = TagRepository(db.conn)

    # Find the tag to rename
    tag = tag_repo.get_by_name(old_name)
    if not tag:
        console.print(f"[red]Tag '{old_name}' not found.[/red]")
        db.close()
        raise typer.Exit(1)

    # Check if new name already exists
    existing = tag_repo.get_by_name(new_name)
    if existing:
        console.print(f"[red]Tag '{new_name}' already exists. Use 'tags merge' to combine tags.[/red]")
        db.close()
        raise typer.Exit(1)

    # Rename the tag
    tag_repo.rename(tag.id, new_name)
    db.close()

    console.print(f"[green]Renamed tag '{old_name}' to '{new_name}'[/green]")


@app.command(name="merge")
def merge_cmd(
    source: str = typer.Argument(..., help="Tag to merge from (will be deleted)"),
    target: str = typer.Argument(..., help="Tag to merge into (will be kept)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Merge one tag into another (source tag is deleted)."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    db = Database(db_path)
    tag_repo = TagRepository(db.conn)

    # Find both tags
    source_tag = tag_repo.get_by_name(source)
    if not source_tag:
        console.print(f"[red]Source tag '{source}' not found.[/red]")
        db.close()
        raise typer.Exit(1)

    target_tag = tag_repo.get_by_name(target)
    if not target_tag:
        console.print(f"[red]Target tag '{target}' not found.[/red]")
        db.close()
        raise typer.Exit(1)

    if source_tag.id == target_tag.id:
        console.print("[red]Source and target tags must be different.[/red]")
        db.close()
        raise typer.Exit(1)

    # Get entry counts
    tag_counts = _get_tag_counts(db)
    source_count = tag_counts.get(source_tag.id, 0)
    target_count = tag_counts.get(target_tag.id, 0)

    # Confirm merge
    if not yes:
        console.print(f"[yellow]Merging '{source}' ({source_count} entries) into '{target}' ({target_count} entries)[/yellow]")
        console.print(f"[yellow]Tag '{source}' will be deleted after merge.[/yellow]")

        confirm = typer.confirm("Proceed with merge?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            db.close()
            raise typer.Exit(0)

    # Perform the merge
    moved_count = tag_repo.merge(source_tag.id, target_tag.id)
    db.close()

    console.print(f"[green]Merged '{source}' into '{target}'[/green]")
    console.print(f"[dim]Moved {moved_count} entries, deleted tag '{source}'.[/dim]")
