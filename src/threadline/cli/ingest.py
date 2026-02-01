"""CLI ingest command."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from threadline.config.paths import get_db_path
from threadline.config.settings import load_settings
from threadline.db.connection import Database
from threadline.ingest.pipeline import IngestPipeline

console = Console()


def ingest_cmd(
    path: Path = typer.Argument(
        ...,
        help="File or directory to ingest",
        exists=True,
        resolve_path=True,
    ),
    no_embeddings: bool = typer.Option(
        False,
        "--no-embeddings",
        help="Skip embedding generation (faster, but no similarity search)",
    ),
    min_chunk_chars: int = typer.Option(
        30,
        "--min-chunk-chars",
        help="Minimum characters for a chunk",
    ),
    ocr: Optional[str] = typer.Option(
        None,
        "--ocr",
        help="OCR method for images: pytesseract (default), trocr (handwriting), vision (LLM-based)",
    ),
) -> None:
    """Ingest journal files from a file or directory."""
    db_path = get_db_path()

    if not db_path.exists():
        console.print("[red]Threadline not initialized. Run 'threadline init' first.[/red]")
        raise typer.Exit(1)

    settings = load_settings()
    db = Database(db_path)

    # Track current stage for progress display
    current_stage = {"name": "", "task_id": None}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=None)

        def progress_callback(stage: str, current: int, total: int) -> None:
            if stage != current_stage["name"]:
                current_stage["name"] = stage
                progress.update(task_id, description=stage, completed=current, total=total)
            else:
                progress.update(task_id, completed=current, total=total)

        pipeline = IngestPipeline(
            db=db,
            settings=settings,
            progress_callback=progress_callback,
        )

        result = pipeline.ingest_path(
            path=path,
            generate_embeddings=not no_embeddings,
            min_chunk_chars=min_chunk_chars,
            ocr_method=ocr,
        )

    db.close()

    # Display results
    console.print()

    if result.errors:
        for error in result.errors[:5]:  # Show first 5 errors
            console.print(f"[red]Error:[/red] {error}")
        if len(result.errors) > 5:
            console.print(f"[dim]...and {len(result.errors) - 5} more errors[/dim]")
        console.print()

    # Summary panel
    summary_lines = [
        f"[green]Files imported:[/green] {result.files_imported}",
        f"[yellow]Files skipped:[/yellow] {result.files_skipped} (duplicates or unsupported)",
        f"[red]Files failed:[/red] {result.files_failed}",
        f"[cyan]Entries created:[/cyan] {result.entries_created}",
    ]

    if not no_embeddings and result.entries_created > 0:
        summary_lines.append(f"[dim]Embeddings generated for all entries[/dim]")

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Ingestion Complete",
            border_style="green" if result.files_failed == 0 else "yellow",
        )
    )

    if result.entries_created > 0:
        console.print()
        console.print("[dim]Next: Run 'threadline browse' to view entries[/dim]")
