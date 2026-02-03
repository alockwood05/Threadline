"""Main Textual application for browsing entries."""

from __future__ import annotations

import os
import subprocess

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Footer, Header, Static, ListItem, ListView, Label, Input, Checkbox, Button
from textual.reactive import reactive
from textual.message import Message

from threadline.db.connection import get_db
from threadline.db.repositories.entries import EntryRepository
from threadline.db.repositories.sources import SourceRepository
from threadline.db.repositories.tags import TagRepository
from threadline.db.repositories.themes import ThemeRepository
from threadline.ingest.models import Entry, Source, Tag, TagCreate, Theme

# Available entry types for filtering
ENTRY_TYPES = [
    "thought",
    "reflection",
    "question",
    "todo list",
    "bullet list",
    "summary",
    "prayer",
]

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

        # Format: title | quote | type badge | tag indicator
        type_badge = get_type_badge(self.entry.entry_type)
        tag_indicator = f" [bright_magenta][{len(self.entry.tags)} tags][/bright_magenta]" if self.entry.tags else ""

        yield Label(f"[bold]{title}[/bold]  {type_badge}{tag_indicator}")
        yield Label(f"[dim]{quote}[/dim]", classes="quote")


class SimilarEntryCard(Static):
    """A card showing a similar entry with similarity score."""

    def __init__(self, entry: Entry, similarity: float, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry
        self.similarity = similarity

    def compose(self) -> ComposeResult:
        title = self.entry.title or "Untitled"
        quote = self.entry.summary_quote or self.entry.content[:60]
        if len(quote) > 60:
            quote = quote[:57] + "..."

        type_badge = get_type_badge(self.entry.entry_type)
        similarity_pct = f"[green]{self.similarity * 100:.1f}%[/green]"

        yield Label(f"{similarity_pct} [bold]{title}[/bold]  {type_badge}")
        yield Label(f"[dim]{quote}[/dim]", classes="quote")


class EntryListItem(ListItem):
    """A list item containing an entry card."""

    def __init__(self, entry: Entry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield EntryCard(self.entry)


class SimilarEntryListItem(ListItem):
    """A list item containing a similar entry card."""

    def __init__(self, entry: Entry, similarity: float, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry
        self.similarity = similarity

    def compose(self) -> ComposeResult:
        yield SimilarEntryCard(self.entry, self.similarity)


class TagCheckbox(Static):
    """A checkbox for a single tag."""

    class Toggled(Message):
        """Message sent when tag is toggled."""

        def __init__(self, tag: Tag, checked: bool) -> None:
            self.tag = tag
            self.checked = checked
            super().__init__()

    def __init__(self, tag: Tag, checked: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tag = tag
        self.checked = checked

    def compose(self) -> ComposeResult:
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = self.tag.color or "white"
        yield Label(f"{checkbox_char} [{color}]{self.tag.name}[/{color}]")

    def on_click(self) -> None:
        """Toggle the checkbox when clicked."""
        self.checked = not self.checked
        # Update display
        label = self.query_one(Label)
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = self.tag.color or "white"
        label.update(f"{checkbox_char} [{color}]{self.tag.name}[/{color}]")
        # Post toggle message
        self.post_message(self.Toggled(self.tag, self.checked))


class EntryTypeCheckbox(Static):
    """A checkbox for filtering by entry type."""

    class Toggled(Message):
        """Message sent when entry type filter is toggled."""

        def __init__(self, entry_type: str, checked: bool) -> None:
            self.entry_type = entry_type
            self.checked = checked
            super().__init__()

    def __init__(self, entry_type: str, checked: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry_type = entry_type
        self.checked = checked

    def compose(self) -> ComposeResult:
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = ENTRY_TYPE_COLORS.get(self.entry_type, "white")
        yield Label(f"{checkbox_char} [{color}]{self.entry_type}[/{color}]")

    def on_click(self) -> None:
        """Toggle the checkbox when clicked."""
        self.checked = not self.checked
        # Update display
        label = self.query_one(Label)
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = ENTRY_TYPE_COLORS.get(self.entry_type, "white")
        label.update(f"{checkbox_char} [{color}]{self.entry_type}[/{color}]")
        # Post toggle message
        self.post_message(self.Toggled(self.entry_type, self.checked))


class FilterTagCheckbox(Static):
    """A checkbox for filtering by tag (separate from the tagging tag picker)."""

    class Toggled(Message):
        """Message sent when tag filter is toggled."""

        def __init__(self, tag: Tag, checked: bool) -> None:
            self.tag = tag
            self.checked = checked
            super().__init__()

    def __init__(self, tag: Tag, checked: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tag = tag
        self.checked = checked

    def compose(self) -> ComposeResult:
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = self.tag.color or "white"
        yield Label(f"{checkbox_char} [{color}]{self.tag.name}[/{color}]")

    def on_click(self) -> None:
        """Toggle the checkbox when clicked."""
        self.checked = not self.checked
        # Update display
        label = self.query_one(Label)
        checkbox_char = "[x]" if self.checked else "[ ]"
        color = self.tag.color or "white"
        label.update(f"{checkbox_char} [{color}]{self.tag.name}[/{color}]")
        # Post toggle message
        self.post_message(self.Toggled(self.tag, self.checked))


class HideTodosToggle(Static):
    """A toggle checkbox for hiding todo entries."""

    class Toggled(Message):
        """Message sent when hide todos is toggled."""

        def __init__(self, checked: bool) -> None:
            self.checked = checked
            super().__init__()

    def __init__(self, checked: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.checked = checked

    def compose(self) -> ComposeResult:
        checkbox_char = "[x]" if self.checked else "[ ]"
        yield Label(f"{checkbox_char} [red]Hide todos[/red]")

    def on_click(self) -> None:
        """Toggle the checkbox when clicked."""
        self.checked = not self.checked
        # Update display
        label = self.query_one(Label)
        checkbox_char = "[x]" if self.checked else "[ ]"
        label.update(f"{checkbox_char} [red]Hide todos[/red]")
        # Post toggle message
        self.post_message(self.Toggled(self.checked))


class ThemeListItem(ListItem):
    """A list item for theme selection."""

    def __init__(self, theme: Theme, **kwargs) -> None:
        super().__init__(**kwargs)
        self.theme = theme

    def compose(self) -> ComposeResult:
        import json

        # Parse keywords JSON to display top 5
        keywords_str = ""
        if self.theme.keywords:
            try:
                keywords = json.loads(self.theme.keywords)
                # keywords is a list of {"word": str, "weight": float}
                top_keywords = keywords[:5]
                keywords_str = ", ".join(kw["word"] for kw in top_keywords)
            except (json.JSONDecodeError, KeyError, TypeError):
                keywords_str = ""

        yield Label(f"[bold]{self.theme.name}[/bold] [dim]({self.theme.entry_count} entries)[/dim]")
        if keywords_str:
            yield Label(f"  [cyan]{keywords_str}[/cyan]", classes="keywords")


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

    #tag-picker {
        display: none;
        width: 40;
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $primary;
        padding: 1;
        layer: overlay;
        dock: right;
    }

    #tag-picker.visible {
        display: block;
    }

    #tag-picker-title {
        text-style: bold;
        padding-bottom: 1;
    }

    #tag-filter {
        margin-bottom: 1;
    }

    #tag-list {
        height: auto;
        max-height: 12;
        overflow-y: auto;
    }

    TagCheckbox {
        height: 1;
        padding: 0 1;
    }

    TagCheckbox:hover {
        background: $primary-background;
    }

    #tag-picker-help {
        color: $text-muted;
        padding-top: 1;
    }

    #filter-panel {
        display: none;
        width: 45;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1;
        layer: overlay;
        dock: right;
    }

    #filter-panel.visible {
        display: block;
    }

    #filter-panel-title {
        text-style: bold;
        padding-bottom: 1;
    }

    .filter-section {
        padding: 1 0;
    }

    .filter-section-title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
    }

    #filter-types {
        height: auto;
        max-height: 10;
        overflow-y: auto;
    }

    #filter-tags {
        height: auto;
        max-height: 8;
        overflow-y: auto;
    }

    EntryTypeCheckbox {
        height: 1;
        padding: 0 1;
    }

    EntryTypeCheckbox:hover {
        background: $primary-background;
    }

    FilterTagCheckbox {
        height: 1;
        padding: 0 1;
    }

    FilterTagCheckbox:hover {
        background: $primary-background;
    }

    HideTodosToggle {
        height: 1;
        padding: 0 1;
        margin-bottom: 1;
    }

    HideTodosToggle:hover {
        background: $primary-background;
    }

    #filter-panel-help {
        color: $text-muted;
        padding-top: 1;
    }

    #similar-panel {
        display: none;
        width: 60;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1;
        layer: overlay;
        dock: right;
    }

    #similar-panel.visible {
        display: block;
    }

    #similar-panel-title {
        text-style: bold;
        padding-bottom: 1;
    }

    #similar-list {
        height: auto;
        max-height: 24;
        overflow-y: auto;
    }

    #similar-panel-help {
        color: $text-muted;
        padding-top: 1;
    }

    #themes-panel {
        display: none;
        width: 60;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1;
        layer: overlay;
        dock: right;
    }

    #themes-panel.visible {
        display: block;
    }

    #themes-panel-title {
        text-style: bold;
        padding-bottom: 1;
    }

    #themes-list {
        height: auto;
        max-height: 24;
        overflow-y: auto;
    }

    ThemeListItem {
        height: auto;
        padding: 0 1;
    }

    ThemeListItem:hover {
        background: $primary-background;
    }

    ThemeListItem .keywords {
        color: $text-muted;
    }

    #themes-panel-help {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "view_entry", "View", show=True),
        Binding("escape", "close_overlay", "Back", show=False),
        Binding("o", "open_source", "Open", show=True),
        Binding("s", "show_similar", "Similar", show=True),
        Binding("t", "toggle_tag_picker", "Tag", show=True),
        Binding("n", "new_tag", "New Tag", show=False),
        Binding("f", "toggle_filter_panel", "Filter", show=True),
        Binding("c", "clear_filters", "Clear", show=False),
        Binding("T", "toggle_themes_panel", "Themes", show=True),
    ]

    # Reactive state
    total_entries: reactive[int] = reactive(0)
    current_offset: reactive[int] = reactive(0)
    page_size: int = 50
    selected_entry: Entry | None = None
    selected_source: Source | None = None

    # Filter state (persists during session)
    _filter_entry_types: set[str]
    _filter_tag_ids: set[int]
    _hide_todos: bool
    _filter_theme_id: int | None

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[Entry] = []
        self._all_loaded = False
        # Initialize filter state
        self._filter_entry_types = set()
        self._filter_tag_ids = set()
        self._hide_todos = False
        self._filter_theme_id = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="status-bar")
        yield ListView(id="entry-list")
        yield Container(
            Static("", id="detail-meta"),
            Static("", id="detail-content"),
            id="detail-view",
        )
        yield Container(
            Static("Tags", id="tag-picker-title"),
            Input(placeholder="Filter tags...", id="tag-filter"),
            Vertical(id="tag-list"),
            Static("[n] New tag  [Esc] Close", id="tag-picker-help"),
            id="tag-picker",
        )
        yield Container(
            Static("Filters", id="filter-panel-title"),
            Container(
                HideTodosToggle(checked=False, id="hide-todos-toggle"),
                classes="filter-section",
            ),
            Container(
                Static("Entry Types", classes="filter-section-title"),
                Vertical(id="filter-types"),
                classes="filter-section",
            ),
            Container(
                Static("Tags", classes="filter-section-title"),
                Vertical(id="filter-tags"),
                classes="filter-section",
            ),
            Static("[c] Clear all  [Esc] Close", id="filter-panel-help"),
            id="filter-panel",
        )
        yield Container(
            Static("Similar Entries", id="similar-panel-title"),
            ListView(id="similar-list"),
            Static("[Enter] View  [Esc] Close", id="similar-panel-help"),
            id="similar-panel",
        )
        yield Container(
            Static("Themes", id="themes-panel-title"),
            ListView(id="themes-list"),
            Static("[Enter] Filter by theme  [Esc] Close", id="themes-panel-help"),
            id="themes-panel",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load initial entries when app starts."""
        self._load_entries()
        self._update_status()

    def _get_active_entry_type_filter(self) -> list[str] | None:
        """Get the active entry type filter, combining explicit selection and hide todos."""
        # Start with explicitly selected entry types (if any)
        selected_types = set(self._filter_entry_types)

        if self._hide_todos:
            # If hiding todos and we have specific types selected, remove todo list from them
            if selected_types:
                selected_types.discard("todo list")
            else:
                # If no specific types selected, include all except todo list
                selected_types = set(ENTRY_TYPES) - {"todo list"}

        # Return None if no filters (show all)
        if not selected_types and not self._hide_todos:
            return None

        return list(selected_types) if selected_types else None

    def _load_entries(self, append: bool = False) -> None:
        """Load entries from database."""
        with get_db() as db:
            repo = EntryRepository(db.conn)

            # Build filter parameters
            entry_types = self._get_active_entry_type_filter()
            tag_ids = list(self._filter_tag_ids) if self._filter_tag_ids else None

            self.total_entries = repo.count(
                entry_types=entry_types, tag_ids=tag_ids, theme_id=self._filter_theme_id
            )

            offset = self.current_offset if append else 0
            entries = repo.list(
                limit=self.page_size,
                offset=offset,
                entry_types=entry_types,
                tag_ids=tag_ids,
                theme_id=self._filter_theme_id,
            )

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
        """Update the status bar with entry count and active filters."""
        status = self.query_one("#status-bar", Static)
        loaded = len(self._entries)

        # Build filter indicator
        filter_parts = []
        if self._hide_todos:
            filter_parts.append("[red]no todos[/red]")
        if self._filter_entry_types:
            type_count = len(self._filter_entry_types)
            filter_parts.append(f"[cyan]{type_count} type{'s' if type_count > 1 else ''}[/cyan]")
        if self._filter_tag_ids:
            tag_count = len(self._filter_tag_ids)
            filter_parts.append(f"[magenta]{tag_count} tag{'s' if tag_count > 1 else ''}[/magenta]")
        if self._filter_theme_id is not None:
            filter_parts.append("[green]theme[/green]")

        if filter_parts:
            filter_text = " | Filters: " + ", ".join(filter_parts)
        else:
            filter_text = ""

        status.update(f"Entries: {loaded}/{self.total_entries}{filter_text}")

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

    def action_close_overlay(self) -> None:
        """Close the filter panel, tag picker, similar panel, themes panel, or detail view (in priority order)."""
        filter_panel = self.query_one("#filter-panel", Container)
        tag_picker = self.query_one("#tag-picker", Container)
        similar_panel = self.query_one("#similar-panel", Container)
        themes_panel = self.query_one("#themes-panel", Container)
        detail_view = self.query_one("#detail-view", Container)
        list_view = self.query_one("#entry-list", ListView)

        # First close filter panel if open
        if filter_panel.has_class("visible"):
            filter_panel.remove_class("visible")
            return

        # Then close tag picker if open
        if tag_picker.has_class("visible"):
            tag_picker.remove_class("visible")
            return

        # Then close similar panel if open
        if similar_panel.has_class("visible"):
            similar_panel.remove_class("visible")
            return

        # Then close themes panel if open
        if themes_panel.has_class("visible"):
            themes_panel.remove_class("visible")
            return

        # Then close detail view if open
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

    def action_toggle_tag_picker(self) -> None:
        """Toggle the tag picker overlay."""
        list_view = self.query_one("#entry-list", ListView)
        detail_view = self.query_one("#detail-view", Container)
        tag_picker = self.query_one("#tag-picker", Container)

        # Get the currently selected entry
        if detail_view.has_class("visible"):
            entry = self.selected_entry
        elif list_view.index is not None and list_view.index < len(self._entries):
            entry = self._entries[list_view.index]
        else:
            return  # No entry selected

        if entry is None:
            return

        if tag_picker.has_class("visible"):
            # Close the tag picker
            tag_picker.remove_class("visible")
        else:
            # Open the tag picker
            self._tagging_entry = entry
            self._refresh_tag_picker()
            tag_picker.add_class("visible")
            # Focus the filter input
            tag_filter = self.query_one("#tag-filter", Input)
            tag_filter.value = ""
            tag_filter.focus()

    def _refresh_tag_picker(self, filter_text: str = "") -> None:
        """Refresh the tag picker list."""
        tag_list = self.query_one("#tag-list", Vertical)
        tag_list.remove_children()

        with get_db() as db:
            tag_repo = TagRepository(db.conn)
            all_tags = tag_repo.list()
            entry_tag_ids = tag_repo.get_entry_tag_ids(self._tagging_entry.id) if hasattr(self, "_tagging_entry") and self._tagging_entry else []

        # Filter tags
        filter_lower = filter_text.lower()
        for tag in all_tags:
            if filter_lower and filter_lower not in tag.name.lower():
                continue
            is_checked = tag.id in entry_tag_ids
            tag_list.mount(TagCheckbox(tag, checked=is_checked))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "tag-filter":
            self._refresh_tag_picker(event.value)

    def on_tag_checkbox_toggled(self, event: TagCheckbox.Toggled) -> None:
        """Handle tag checkbox toggle."""
        if not hasattr(self, "_tagging_entry") or self._tagging_entry is None:
            return

        with get_db() as db:
            tag_repo = TagRepository(db.conn)
            if event.checked:
                tag_repo.add_tag_to_entry(self._tagging_entry.id, event.tag.id)
            else:
                tag_repo.remove_tag_from_entry(self._tagging_entry.id, event.tag.id)

            # Update the entry's tags list
            entry_repo = EntryRepository(db.conn)
            updated_entry = entry_repo.get(self._tagging_entry.id)
            if updated_entry:
                self._tagging_entry.tags = updated_entry.tags
                # Update the entry in the list too
                for i, e in enumerate(self._entries):
                    if e.id == self._tagging_entry.id:
                        self._entries[i].tags = updated_entry.tags
                        break

        # Refresh the list item display
        self._refresh_entry_display(self._tagging_entry.id)

        # Update detail view if visible
        detail_view = self.query_one("#detail-view", Container)
        if detail_view.has_class("visible") and self.selected_entry and self.selected_entry.id == self._tagging_entry.id:
            self.selected_entry = self._tagging_entry
            self._update_detail_meta()

    def _refresh_entry_display(self, entry_id: int) -> None:
        """Refresh the display of a specific entry in the list."""
        list_view = self.query_one("#entry-list", ListView)
        try:
            item = self.query_one(f"#entry-{entry_id}", EntryListItem)
            # Find the entry and rebuild the item
            for entry in self._entries:
                if entry.id == entry_id:
                    # Replace the list item
                    index = list(list_view.children).index(item)
                    item.remove()
                    new_item = EntryListItem(entry, id=f"entry-{entry.id}")
                    list_view.mount(new_item, before=index)
                    list_view.index = index
                    break
        except Exception:
            pass  # Item not found, ignore

    def _update_detail_meta(self) -> None:
        """Update the detail view metadata."""
        if not self.selected_entry:
            return

        detail_meta = self.query_one("#detail-meta", Static)
        entry = self.selected_entry

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

    def action_new_tag(self) -> None:
        """Create a new tag from the filter input."""
        tag_picker = self.query_one("#tag-picker", Container)
        if not tag_picker.has_class("visible"):
            return

        tag_filter = self.query_one("#tag-filter", Input)
        new_tag_name = tag_filter.value.strip()

        if not new_tag_name:
            return

        with get_db() as db:
            tag_repo = TagRepository(db.conn)
            # Check if tag already exists
            existing = tag_repo.get_by_name(new_tag_name)
            if existing:
                # Tag already exists, just refresh to show it
                self._refresh_tag_picker()
                return

            # Create new tag
            tag_create = TagCreate(name=new_tag_name)
            tag_repo.create(tag_create)

        # Refresh the picker to show the new tag
        tag_filter.value = ""
        self._refresh_tag_picker()

    def action_toggle_filter_panel(self) -> None:
        """Toggle the filter panel overlay."""
        filter_panel = self.query_one("#filter-panel", Container)

        if filter_panel.has_class("visible"):
            filter_panel.remove_class("visible")
        else:
            self._refresh_filter_panel()
            filter_panel.add_class("visible")

    def _refresh_filter_panel(self) -> None:
        """Refresh the filter panel with current state."""
        # Refresh entry type checkboxes
        filter_types = self.query_one("#filter-types", Vertical)
        filter_types.remove_children()
        for entry_type in ENTRY_TYPES:
            is_checked = entry_type in self._filter_entry_types
            filter_types.mount(EntryTypeCheckbox(entry_type, checked=is_checked))

        # Refresh tag checkboxes
        filter_tags = self.query_one("#filter-tags", Vertical)
        filter_tags.remove_children()
        with get_db() as db:
            tag_repo = TagRepository(db.conn)
            all_tags = tag_repo.list()
        for tag in all_tags:
            is_checked = tag.id in self._filter_tag_ids
            filter_tags.mount(FilterTagCheckbox(tag, checked=is_checked))

        # Update hide todos toggle display
        hide_todos_toggle = self.query_one("#hide-todos-toggle", HideTodosToggle)
        hide_todos_toggle.checked = self._hide_todos
        label = hide_todos_toggle.query_one(Label)
        checkbox_char = "[x]" if self._hide_todos else "[ ]"
        label.update(f"{checkbox_char} [red]Hide todos[/red]")

    def on_entry_type_checkbox_toggled(self, event: EntryTypeCheckbox.Toggled) -> None:
        """Handle entry type filter toggle."""
        if event.checked:
            self._filter_entry_types.add(event.entry_type)
        else:
            self._filter_entry_types.discard(event.entry_type)
        self._apply_filters()

    def on_filter_tag_checkbox_toggled(self, event: FilterTagCheckbox.Toggled) -> None:
        """Handle tag filter toggle."""
        if event.checked:
            self._filter_tag_ids.add(event.tag.id)
        else:
            self._filter_tag_ids.discard(event.tag.id)
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filters and reload entries."""
        # Reset pagination state
        self.current_offset = 0
        self._all_loaded = False
        # Reload entries with filters
        self._load_entries(append=False)
        self._update_status()

    def action_clear_filters(self) -> None:
        """Clear all active filters."""
        self._filter_entry_types.clear()
        self._filter_tag_ids.clear()
        self._hide_todos = False
        self._filter_theme_id = None

        # Refresh filter panel if visible
        filter_panel = self.query_one("#filter-panel", Container)
        if filter_panel.has_class("visible"):
            self._refresh_filter_panel()

        self._apply_filters()

    def on_hide_todos_toggle_toggled(self, event: HideTodosToggle.Toggled) -> None:
        """Handle hide todos toggle."""
        self._hide_todos = event.checked
        self._apply_filters()

    def action_show_similar(self) -> None:
        """Show similar entries for the current entry."""
        detail_view = self.query_one("#detail-view", Container)

        # Only works in detail view
        if not detail_view.has_class("visible"):
            return

        if self.selected_entry is None:
            return

        # Check if entry has embedding
        if not self.selected_entry.embedding:
            return

        similar_panel = self.query_one("#similar-panel", Container)

        if similar_panel.has_class("visible"):
            # Close the panel
            similar_panel.remove_class("visible")
        else:
            # Open the panel and populate with similar entries
            self._refresh_similar_panel()
            similar_panel.add_class("visible")

    def _refresh_similar_panel(self) -> None:
        """Refresh the similar entries panel."""
        if not self.selected_entry:
            return

        similar_list = self.query_one("#similar-list", ListView)
        similar_list.clear()

        with get_db() as db:
            repo = EntryRepository(db.conn)
            similar_entries = repo.find_similar(self.selected_entry.id, limit=10)

        if not similar_entries:
            similar_list.append(ListItem(Static("[yellow]No similar entries found[/yellow]")))
            return

        for entry, similarity in similar_entries:
            similar_list.append(SimilarEntryListItem(entry, similarity, id=f"similar-{entry.id}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection in the similar or themes lists."""
        # Check if this is the similar list
        if event.list_view.id == "similar-list":
            # Get the selected item
            if event.item and hasattr(event.item, "entry"):
                entry = event.item.entry  # type: ignore
                # Close the similar panel
                similar_panel = self.query_one("#similar-panel", Container)
                similar_panel.remove_class("visible")
                # Show the selected entry
                self.selected_entry = entry
                self._show_detail(entry)

        # Check if this is the themes list
        elif event.list_view.id == "themes-list":
            if event.item and hasattr(event.item, "theme"):
                theme = event.item.theme  # type: ignore
                # Close the themes panel
                themes_panel = self.query_one("#themes-panel", Container)
                themes_panel.remove_class("visible")
                # Set theme filter and reload
                self._filter_theme_id = theme.id
                self._apply_filters()

    def action_toggle_themes_panel(self) -> None:
        """Toggle the themes panel overlay."""
        themes_panel = self.query_one("#themes-panel", Container)

        if themes_panel.has_class("visible"):
            themes_panel.remove_class("visible")
        else:
            self._refresh_themes_panel()
            themes_panel.add_class("visible")

    def _refresh_themes_panel(self) -> None:
        """Refresh the themes panel with all themes."""
        themes_list = self.query_one("#themes-list", ListView)
        themes_list.clear()

        with get_db() as db:
            theme_repo = ThemeRepository(db.conn)
            themes = theme_repo.list(limit=100)

        if not themes:
            themes_list.append(ListItem(Static("[yellow]No themes found. Run 'threadline extract-themes' first.[/yellow]")))
            return

        for theme in themes:
            themes_list.append(ThemeListItem(theme, id=f"theme-{theme.id}"))


def run_browse() -> None:
    """Run the browse TUI application."""
    app = ThreadlineApp()
    app.run()
