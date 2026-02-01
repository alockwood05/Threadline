"""CLI init command."""

import typer
from rich.console import Console
from rich.panel import Panel

from threadline.config.paths import (
    get_threadline_dir,
    get_db_path,
    get_originals_dir,
    get_models_dir,
    get_config_path,
    ensure_directories,
)
from threadline.config.settings import Settings, save_settings
from threadline.db.connection import init_database

console = Console()


def init_cmd(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Reinitialize even if already initialized",
    ),
) -> None:
    """Initialize Threadline data directory and database."""
    threadline_dir = get_threadline_dir()
    db_path = get_db_path()
    config_path = get_config_path()

    # Check if already initialized
    if db_path.exists() and not force:
        console.print(
            f"[yellow]Threadline already initialized at {threadline_dir}[/yellow]"
        )
        console.print("Use --force to reinitialize")
        raise typer.Exit(1)

    console.print(f"Initializing Threadline at [cyan]{threadline_dir}[/cyan]")

    # Create directories
    ensure_directories()
    console.print(f"  [green]✓[/green] Created directories")

    # Initialize database
    db = init_database(db_path)
    vss_status = "[green]enabled[/green]" if db.vss_available else "[yellow]not available[/yellow]"
    console.print(f"  [green]✓[/green] Created database (vector search: {vss_status})")
    db.close()

    # Create default config if it doesn't exist
    if not config_path.exists():
        save_settings(Settings(), config_path)
        console.print(f"  [green]✓[/green] Created default config")

    # Summary
    console.print()
    console.print(
        Panel(
            f"""[bold]Threadline initialized![/bold]

[dim]Data directory:[/dim] {threadline_dir}
[dim]Database:[/dim] {db_path}
[dim]Originals:[/dim] {get_originals_dir()}
[dim]Models:[/dim] {get_models_dir()}
[dim]Config:[/dim] {config_path}

Next steps:
  [cyan]threadline ingest <path>[/cyan]  Import journal files
  [cyan]threadline browse[/cyan]         Browse entries (TUI)
""",
            title="Setup Complete",
            border_style="green",
        )
    )
