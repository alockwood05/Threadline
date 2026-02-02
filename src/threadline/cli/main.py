"""Main CLI application."""

import typer
from rich.console import Console

from threadline import __version__

app = typer.Typer(
    name="threadline",
    help="Local-first journal entry management system",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"threadline version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Threadline - Local-first journal entry management."""
    pass


# Import and register commands
from threadline.cli.init import init_cmd
from threadline.cli.ingest import ingest_cmd
from threadline.cli.stats import stats_cmd
from threadline.cli.browse import browse_cmd
from threadline.cli.themes import extract_themes_cmd

app.command(name="init")(init_cmd)
app.command(name="ingest")(ingest_cmd)
app.command(name="stats")(stats_cmd)
app.command(name="browse")(browse_cmd)
app.command(name="extract-themes")(extract_themes_cmd)


if __name__ == "__main__":
    app()
