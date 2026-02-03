"""CLI command for re-processing entries."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

from threadline.config.paths import get_db_path, get_models_dir
from threadline.config.settings import load_settings
from threadline.db.connection import Database
from threadline.db.repositories.entries import EntryRepository

console = Console()


def reprocess_cmd(
    embeddings: bool = typer.Option(
        False,
        "--embeddings",
        help="Regenerate embeddings for all entries",
    ),
    classify: bool = typer.Option(
        False,
        "--classify",
        help="Re-run classification on all entries",
    ),
    themes: bool = typer.Option(
        False,
        "--themes",
        help="Re-extract themes (alias for extract-themes --force)",
    ),
) -> None:
    """
    Re-run processing on existing entries.

    Useful after model upgrades or configuration changes.

    Examples:
        threadline reprocess --embeddings    # Regenerate all embeddings
        threadline reprocess --classify      # Re-classify all entries
        threadline reprocess --themes        # Re-extract themes
    """
    # Check that at least one option was specified
    if not any([embeddings, classify, themes]):
        console.print("[yellow]No processing option specified.[/yellow]")
        console.print()
        console.print("Available options:")
        console.print("  --embeddings  Regenerate embeddings for all entries")
        console.print("  --classify    Re-run classification on all entries")
        console.print("  --themes      Re-extract themes")
        raise typer.Exit(1)

    db_path = get_db_path()
    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    settings = load_settings()
    db = Database(db_path)
    entry_repo = EntryRepository(db.conn)

    # Count entries
    total_entries = entry_repo.count()
    if total_entries == 0:
        console.print("[yellow]No entries found. Run 'threadline ingest' first.[/yellow]")
        db.close()
        raise typer.Exit(1)

    try:
        if embeddings:
            _reprocess_embeddings(db, entry_repo, settings, total_entries)

        if classify:
            _reprocess_classification(db, entry_repo, settings, total_entries)

        if themes:
            db.close()
            _reprocess_themes()
            return  # themes handles its own exit
    finally:
        if not themes:
            db.close()


def _reprocess_embeddings(
    db: Database,
    entry_repo: EntryRepository,
    settings,
    total_entries: int,
) -> None:
    """Regenerate embeddings for all entries."""
    from threadline.core.embedder import Embedder

    console.print(f"[dim]Regenerating embeddings for {total_entries} entries...[/dim]")
    console.print(f"[dim]Model: {settings.embeddings.model}[/dim]")

    # Initialize embedder
    cache_dir = get_models_dir()
    embedder = Embedder(
        model_name=settings.embeddings.model,
        cache_dir=cache_dir,
    )

    # Load all entries in batches
    batch_size = 100
    processed = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Generating embeddings...", total=total_entries)

        offset = 0
        while offset < total_entries:
            entries = entry_repo.list(limit=batch_size, offset=offset)
            if not entries:
                break

            # Generate embeddings for batch
            texts = [e.content for e in entries]
            try:
                embeddings_list = embedder.embed_texts(texts, batch_size=32)

                # Update each entry
                for entry, embedding in zip(entries, embeddings_list):
                    entry_repo.update_embedding(entry.id, embedding)
                    processed += 1

            except Exception as e:
                errors.append(f"Batch at offset {offset}: {e}")
                processed += len(entries)

            offset += len(entries)
            progress.update(task_id, completed=processed)

    # Display results
    console.print()
    summary_lines = [
        f"Entries processed: {processed}",
        f"Model: {settings.embeddings.model}",
    ]

    if errors:
        summary_lines.append(f"[red]Errors: {len(errors)}[/red]")

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Embedding Regeneration Complete",
            border_style="green" if not errors else "yellow",
        )
    )

    if errors:
        for error in errors[:5]:
            console.print(f"[red]Error:[/red] {error}")
        if len(errors) > 5:
            console.print(f"[dim]...and {len(errors) - 5} more errors[/dim]")


def _reprocess_classification(
    db: Database,
    entry_repo: EntryRepository,
    settings,
    total_entries: int,
) -> None:
    """Re-run classification on all entries."""
    from threadline.core.classifier import Classifier

    console.print(f"[dim]Re-classifying {total_entries} entries...[/dim]")
    console.print(f"[dim]Model: {settings.classification.model}[/dim]")

    # Initialize classifier
    cache_dir = get_models_dir()
    classifier = Classifier(
        model_name=settings.classification.model,
        labels=settings.classification.labels,
        confidence_threshold=settings.classification.confidence_threshold,
        cache_dir=cache_dir,
    )

    # Track before/after changes
    changes: list[dict] = []
    batch_size = 100
    processed = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Classifying entries...", total=total_entries)

        offset = 0
        while offset < total_entries:
            entries = entry_repo.list(limit=batch_size, offset=offset)
            if not entries:
                break

            # Classify batch
            texts = [e.content for e in entries]
            try:
                classifications = classifier.classify_texts(texts, batch_size=8)

                # Update each entry and track changes
                for entry, (new_type, new_confidence) in zip(entries, classifications):
                    old_type = entry.entry_type
                    old_confidence = entry.entry_type_confidence

                    if old_type != new_type:
                        changes.append({
                            "entry_id": entry.id,
                            "old_type": old_type,
                            "old_confidence": old_confidence,
                            "new_type": new_type,
                            "new_confidence": new_confidence,
                            "content_preview": entry.content[:50] + "..." if len(entry.content) > 50 else entry.content,
                        })

                    entry_repo.update_classification(entry.id, new_type, new_confidence)
                    processed += 1

            except Exception as e:
                errors.append(f"Batch at offset {offset}: {e}")
                processed += len(entries)

            offset += len(entries)
            progress.update(task_id, completed=processed)

    # Display results
    console.print()

    summary_lines = [
        f"Entries processed: {processed}",
        f"Classifications changed: {len(changes)}",
        f"Model: {settings.classification.model}",
    ]

    if errors:
        summary_lines.append(f"[red]Errors: {len(errors)}[/red]")

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Classification Complete",
            border_style="green" if not errors else "yellow",
        )
    )

    # Show before/after comparison for changed entries
    if changes:
        console.print()
        table = Table(title=f"Classification Changes ({len(changes)} entries)")
        table.add_column("Entry ID", style="dim")
        table.add_column("Old Type")
        table.add_column("New Type")
        table.add_column("Confidence")
        table.add_column("Preview")

        # Show first 20 changes
        for change in changes[:20]:
            old_conf = f"{change['old_confidence']:.2f}" if change['old_confidence'] else "N/A"
            new_conf = f"{change['new_confidence']:.2f}"
            table.add_row(
                str(change["entry_id"]),
                change["old_type"] or "[dim]None[/dim]",
                change["new_type"],
                f"{old_conf} → {new_conf}",
                change["content_preview"],
            )

        console.print(table)

        if len(changes) > 20:
            console.print(f"\n[dim]... and {len(changes) - 20} more changes[/dim]")

    if errors:
        console.print()
        for error in errors[:5]:
            console.print(f"[red]Error:[/red] {error}")
        if len(errors) > 5:
            console.print(f"[dim]...and {len(errors) - 5} more errors[/dim]")


def _reprocess_themes() -> None:
    """Re-extract themes (runs extract-themes --force)."""
    console.print("[dim]Re-extracting themes...[/dim]")
    console.print()

    # Import and run extract_themes_cmd with force=True
    from threadline.cli.themes import extract_themes_cmd

    # Call extract_themes_cmd directly with force=True
    extract_themes_cmd(force=True)
