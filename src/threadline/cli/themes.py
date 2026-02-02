"""CLI command for theme extraction."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

import numpy as np

from threadline.config.paths import get_db_path
from threadline.config.settings import load_settings
from threadline.db.connection import Database
from threadline.db.repositories.entries import EntryRepository
from threadline.db.repositories.themes import ThemeRepository
from threadline.models.embedding import bytes_to_embedding
from threadline.core.theme_extractor import (
    ThemeExtractor,
    keywords_to_json,
    entry_ids_to_json,
)
from threadline.ingest.models import ThemeCreate, ThemeExtractionResult

console = Console()


def extract_themes_cmd(
    min_topic_size: int = typer.Option(
        None,
        "--min-topic-size",
        help="Minimum entries per topic (default: from config, typically 5)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Clear existing themes before extraction",
    ),
) -> None:
    """
    Extract themes from entries using BERTopic.

    Uses stored embeddings to cluster entries into topics automatically.
    Themes are extracted locally using UMAP + HDBSCAN + c-TF-IDF.
    """
    db_path = get_db_path()
    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    settings = load_settings()
    db = Database(db_path)

    # Get configuration
    config_min_topic_size = settings.themes.min_topic_size
    actual_min_topic_size = min_topic_size if min_topic_size is not None else config_min_topic_size
    nr_topics = settings.themes.nr_topics

    # Initialize repositories
    entry_repo = EntryRepository(db.conn)
    theme_repo = ThemeRepository(db.conn)

    # Check if themes already exist
    existing_count = theme_repo.count()
    if existing_count > 0 and not force:
        console.print(
            f"[yellow]Found {existing_count} existing themes. "
            f"Use --force to clear and re-extract.[/yellow]"
        )
        raise typer.Exit(1)

    # Clear existing themes if force flag is set
    if force and existing_count > 0:
        console.print(f"[dim]Clearing {existing_count} existing themes...[/dim]")
        theme_repo.clear_all()

    # Load all entries with embeddings
    console.print("[dim]Loading entries with embeddings...[/dim]")

    # Get total count first
    total_entries = entry_repo.count()
    if total_entries == 0:
        console.print("[yellow]No entries found. Run 'threadline ingest' first.[/yellow]")
        db.close()
        raise typer.Exit(1)

    # Load entries in batches
    entries = []
    batch_size = 1000
    offset = 0

    while True:
        batch = entry_repo.list(limit=batch_size, offset=offset)
        if not batch:
            break
        entries.extend(batch)
        offset += len(batch)
        if len(batch) < batch_size:
            break

    # Filter entries with embeddings
    entries_with_embeddings = [e for e in entries if e.embedding is not None]

    if len(entries_with_embeddings) == 0:
        console.print("[yellow]No entries with embeddings found. Run 'threadline ingest' first.[/yellow]")
        db.close()
        raise typer.Exit(1)

    if len(entries_with_embeddings) < actual_min_topic_size:
        console.print(
            f"[yellow]Need at least {actual_min_topic_size} entries for theme extraction, "
            f"got {len(entries_with_embeddings)}. "
            f"Try --min-topic-size with a smaller value.[/yellow]"
        )
        db.close()
        raise typer.Exit(1)

    console.print(
        f"[dim]Found {len(entries_with_embeddings)} entries with embeddings "
        f"(out of {total_entries} total)[/dim]"
    )

    # Extract documents and embeddings
    documents = [e.content for e in entries_with_embeddings]
    entry_ids = [e.id for e in entries_with_embeddings]

    # Convert embeddings from bytes to numpy array
    # Determine embedding dimensions from first entry
    first_embedding = bytes_to_embedding(entries_with_embeddings[0].embedding)  # type: ignore
    dimensions = len(first_embedding)

    embeddings_list = []
    for entry in entries_with_embeddings:
        emb = bytes_to_embedding(entry.embedding, dimensions)  # type: ignore
        embeddings_list.append(emb)

    embeddings = np.array(embeddings_list, dtype=np.float32)

    # Create theme extractor
    try:
        extractor = ThemeExtractor(
            min_topic_size=actual_min_topic_size,
            nr_topics=nr_topics,
        )
    except ImportError as e:
        console.print(
            f"[red]{e}[/red]\n\n"
            "[yellow]Install theme extraction dependencies with:[/yellow]\n"
            "  pip install threadline[ml-full]"
        )
        db.close()
        raise typer.Exit(1)

    # Run extraction with progress
    result = ThemeExtractionResult()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Extracting themes...", total=3)

        def progress_callback(stage: str, current: int, total: int) -> None:
            progress.update(task_id, description=stage, completed=current, total=total)

        try:
            output = extractor.extract_themes(
                documents=documents,
                embeddings=embeddings,
                progress_callback=progress_callback,
            )
        except Exception as e:
            console.print(f"[red]Theme extraction failed: {e}[/red]")
            db.close()
            raise typer.Exit(1)

    # Store themes in database
    console.print("[dim]Storing themes in database...[/dim]")

    # Create a mapping from topic_id to database theme_id
    topic_to_theme_id: dict[int, int] = {}

    for topic in output.topics:
        # Convert representative doc indices to entry IDs
        rep_entry_ids = [entry_ids[idx] for idx in topic.representative_doc_indices]

        theme_create = ThemeCreate(
            topic_id=topic.topic_id,
            name=topic.name,
            keywords=keywords_to_json(topic.keywords) if topic.keywords else None,
            representative_docs=entry_ids_to_json(rep_entry_ids) if rep_entry_ids else None,
            entry_count=topic.entry_count,
        )
        theme_id = theme_repo.create(theme_create)
        topic_to_theme_id[topic.topic_id] = theme_id
        result.themes_created += 1

    # Store entry-theme assignments
    console.print("[dim]Assigning entries to themes...[/dim]")

    assignments_batch = []
    for i, (topic_id, probability) in enumerate(output.assignments):
        entry_id = entry_ids[i]
        if topic_id in topic_to_theme_id:
            theme_id = topic_to_theme_id[topic_id]
            assignments_batch.append((entry_id, theme_id, probability))
            if topic_id == -1:
                result.outlier_entries += 1
            else:
                result.entries_assigned += 1

    # Batch insert assignments
    if assignments_batch:
        theme_repo.add_entries_to_theme_batch(assignments_batch)

    # Record model run
    theme_repo.record_model_run(
        model_name="BERTopic",
        model_version=None,
        entries_processed=len(entries_with_embeddings),
    )

    db.close()

    # Display results
    console.print()

    # Create summary panel
    summary_lines = [
        f"Themes extracted: {result.themes_created}",
        f"Entries assigned: {result.entries_assigned}",
        f"Outlier entries: {result.outlier_entries}",
        f"Min topic size: {actual_min_topic_size}",
    ]

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Theme Extraction Complete",
            border_style="green",
        )
    )

    # Show themes table
    if output.topics:
        table = Table(title="Extracted Themes")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Entries", justify="right")
        table.add_column("Top Keywords")

        # Sort by entry count, exclude outliers from top display
        sorted_topics = sorted(
            [t for t in output.topics if t.topic_id != -1],
            key=lambda t: t.entry_count,
            reverse=True,
        )

        for topic in sorted_topics[:10]:  # Show top 10
            keywords_str = ", ".join(kw["word"] for kw in topic.keywords[:5])
            table.add_row(
                str(topic.topic_id),
                topic.name,
                str(topic.entry_count),
                keywords_str,
            )

        # Add outliers row if any
        outlier_topic = next((t for t in output.topics if t.topic_id == -1), None)
        if outlier_topic and outlier_topic.entry_count > 0:
            table.add_row(
                "-1",
                "[dim]Outliers[/dim]",
                str(outlier_topic.entry_count),
                "[dim]unclustered entries[/dim]",
            )

        console.print()
        console.print(table)

        if len(sorted_topics) > 10:
            console.print(f"\n[dim]... and {len(sorted_topics) - 10} more themes[/dim]")
