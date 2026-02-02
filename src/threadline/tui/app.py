"""Main Textual application for browsing entries."""

from __future__ import annotations

import os
import subprocess

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static, ListItem, ListView, Label, Input, Checkbox
from textual.reactive import reactive
from textual.message import Message

from threadline.db.connection import get_db
from threadline.db.repositories.entries import EntryRepository
from threadline.db.repositories.sources import SourceRepository
from threadline.db.repositories.tags import TagRepository
from threadline.ingest.models import Entry, Source, Tag, TagCreate

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


class EntryListItem(ListItem):
    """A list item containing an entry card."""

    def __init__(self, entry: Entry, **kwargs) -> None:
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield EntryCard(self.entry)


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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "view_entry", "View", show=True),
        Binding("escape", "close_detail_or_tag_picker", "Back", show=False),
        Binding("o", "open_source", "Open", show=True),
        Binding("t", "toggle_tag_picker", "Tag", show=True),
        Binding("n", "new_tag", "New Tag", show=False),
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
        yield Container(
            Static("Tags", id="tag-picker-title"),
            Input(placeholder="Filter tags...", id="tag-filter"),
            Vertical(id="tag-list"),
            Static("[n] New tag  [Esc] Close", id="tag-picker-help"),
            id="tag-picker",
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

    def action_close_detail_or_tag_picker(self) -> None:
        """Close the tag picker or detail view."""
        tag_picker = self.query_one("#tag-picker", Container)
        detail_view = self.query_one("#detail-view", Container)
        list_view = self.query_one("#entry-list", ListView)

        # First close tag picker if open
        if tag_picker.has_class("visible"):
            tag_picker.remove_class("visible")
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


def run_browse() -> None:
    """Run the browse TUI application."""
    app = ThreadlineApp()
    app.run()
