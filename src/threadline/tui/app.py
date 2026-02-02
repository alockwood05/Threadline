"""Main Textual application for browsing entries."""

from __future__ import annotations

import os
import subprocess

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Footer, Header, Static, ListItem, ListView, Label
from textual.reactive import reactive

from threadline.db.connection import get_db
from threadline.db.repositories.entries import EntryRepository
from threadline.db.repositories.sources import SourceRepository
from threadline.ingest.models import Entry, Source

# Color mapping for entry types
ENTRY_TYPE_COLORS = {
    "thought": "cyan",
    "reflection": "blue",
    "question": "yellow",
    "todo list": "red",
    "bullet list": "magenta",
    "summary": "green",
    "prayer": "bright_blue",
}


def get_type_badge(entry_type: str | None) -> str:
    """Get a color-coded badge for the entry type."""
    if not entry_type:
        return ""
    color = ENTRY_TYPE_COLORS.get(entry_type, "white")
    return f"[{color}][{entry_type}][/{color}]"


class EntryCard(Static):
    """A single entry display card."""

    def __init__(self, entry: Entry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self) -> ComposeResult:
        # Build the display text
        title = self.entry.title or "Untitled"
        quote = self.entry.summary_quote or self.entry.content[:80]
        if len(quote) > 80:
            quote = quote[:77] + "..."

        # Format: title | quote | type badge
        type_badge = get_type_badge(self.entry.entry_type)

        yield Label(f"[bold]{title}[/bold]  {type_badge}")
        yield Label(f"[dim]{quote}[/dim]", classes="quote")


class EntryListItem(ListItem):
    """A list item containing an entry card."""

    def __init__(self, entry: Entry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield EntryCard(self.entry)


class ThreadlineApp(App):
    """Main Threadline browsing application."""

    TITLE = "Threadline"
    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        dock: top;
    }

    Footer {
        dock: bottom;
    }

    #entry-list {
        height: 1fr;
    }

    EntryCard {
        padding: 0 1;
        height: auto;
    }

    EntryCard .quote {
        color: $text-muted;
    }

    ListItem {
        padding: 0;
    }

    ListItem:hover {
        background: $primary-background;
    }

    ListItem.-highlight {
        background: $accent;
    }

    #status-bar {
        dock: top;
        height: 1;
        background: $primary-background;
        padding: 0 1;
    }

    #detail-view {
        display: none;
        padding: 1 2;
    }

    #detail-view.visible {
        display: block;
    }

    #detail-content {
        padding: 1;
    }

    #detail-meta {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "view_entry", "View", show=True),
        Binding("escape", "close_detail", "Back", show=False),
        Binding("o", "open_source", "Open", show=True),
    ]

    # Reactive state
    total_entries: reactive[int] = reactive(0)
    current_offset: reactive[int] = reactive(0)
    page_size: int = 50
    selected_entry: Entry | None = None
    selected_source: Source | None = None

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[Entry] = []
        self._all_loaded = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="status-bar")
        yield ListView(id="entry-list")
        yield Container(
            Static("", id="detail-meta"),
            Static("", id="detail-content"),
            id="detail-view",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load initial entries when app starts."""
        self._load_entries()
        self._update_status()

    def _load_entries(self, append: bool = False) -> None:
        """Load entries from database."""
        with get_db() as db:
            repo = EntryRepository(db.conn)
            self.total_entries = repo.count()

            offset = self.current_offset if append else 0
            entries = repo.list(limit=self.page_size, offset=offset)

            if not append:
                self._entries = entries
            else:
                self._entries.extend(entries)

            # Check if all entries loaded
            if len(entries) < self.page_size:
                self._all_loaded = True

        # Update the list view
        list_view = self.query_one("#entry-list", ListView)
        if not append:
            list_view.clear()

        for entry in entries:
            list_view.append(EntryListItem(entry, id=f"entry-{entry.id}"))

    def _update_status(self) -> None:
        """Update the status bar."""
        status = self.query_one("#status-bar", Static)
        loaded = len(self._entries)
        status.update(f"Entries: {loaded}/{self.total_entries}")

    def action_cursor_down(self) -> None:
        """Move cursor down in the list."""
        list_view = self.query_one("#entry-list", ListView)
        list_view.action_cursor_down()
        self._maybe_load_more()

    def action_cursor_up(self) -> None:
        """Move cursor up in the list."""
        list_view = self.query_one("#entry-list", ListView)
        list_view.action_cursor_up()

    def _maybe_load_more(self) -> None:
        """Load more entries if near the end of the list."""
        if self._all_loaded:
            return

        list_view = self.query_one("#entry-list", ListView)
        if list_view.index is not None:
            # Load more when within 10 items of the end
            if list_view.index >= len(self._entries) - 10:
                self.current_offset = len(self._entries)
                self._load_entries(append=True)
                self._update_status()

    def action_view_entry(self) -> None:
        """View the selected entry in detail."""
        list_view = self.query_one("#entry-list", ListView)
        if list_view.index is not None and list_view.index < len(self._entries):
            entry = self._entries[list_view.index]
            self.selected_entry = entry
            self._show_detail(entry)

    def _show_detail(self, entry: Entry) -> None:
        """Show entry detail view."""
        detail_view = self.query_one("#detail-view", Container)
        detail_meta = self.query_one("#detail-meta", Static)
        detail_content = self.query_one("#detail-content", Static)
        list_view = self.query_one("#entry-list", ListView)

        # Fetch the source for this entry
        with get_db() as db:
            source_repo = SourceRepository(db.conn)
            self.selected_source = source_repo.get(entry.source_id)

        # Build metadata
        meta_parts = []
        if entry.entry_date:
            meta_parts.append(f"Date: {entry.entry_date.isoformat()}")
        if entry.entry_type:
            confidence = entry.entry_type_confidence or 0
            uncertain = " (uncertain)" if confidence < 0.7 else ""
            meta_parts.append(f"Type: {entry.entry_type}{uncertain}")
        if entry.location:
            meta_parts.append(f"Location: {entry.location}")
        if entry.tags:
            meta_parts.append(f"Tags: {', '.join(entry.tags)}")
        if self.selected_source:
            meta_parts.append(f"Source: {self.selected_source.filepath}")

        meta_text = " | ".join(meta_parts) if meta_parts else "No metadata"
        detail_meta.update(meta_text)
        detail_content.update(entry.content)

        # Show detail, hide list
        list_view.display = False
        detail_view.add_class("visible")

    def action_close_detail(self) -> None:
        """Close the detail view and return to list."""
        detail_view = self.query_one("#detail-view", Container)
        list_view = self.query_one("#entry-list", ListView)

        if detail_view.has_class("visible"):
            detail_view.remove_class("visible")
            list_view.display = True
            self.selected_entry = None
            self.selected_source = None

    def action_open_source(self) -> None:
        """Open the source file in $EDITOR."""
        detail_view = self.query_one("#detail-view", Container)

        # Only works in detail view
        if not detail_view.has_class("visible"):
            return

        if self.selected_source is None:
            return

        # Get editor from environment, default to vim
        editor = os.environ.get("EDITOR", "vim")
        filepath = self.selected_source.filepath

        # Suspend the app and open the editor
        with self.suspend():
            subprocess.run([editor, filepath])


def run_browse() -> None:
    """Run the browse TUI application."""
    app = ThreadlineApp()
    app.run()
