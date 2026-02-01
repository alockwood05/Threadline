"""Browse command for launching the TUI."""

from __future__ import annotations

import typer
from rich.console import Console

from threadline.config.paths import get_db_path

console = Console()


def browse_cmd() -> None:
    """Launch the interactive entry browser."""
    # Check if database exists
    db_path = get_db_path()
    if not db_path.exists():
        console.print(
            "[red]Error:[/red] Threadline not initialized. "
            "Run 'threadline init' first."
        )
        raise typer.Exit(1)

    # Import here to avoid slow import on startup
    from threadline.tui.app import run_browse

    run_browse()
