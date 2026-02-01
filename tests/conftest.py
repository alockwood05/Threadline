"""Pytest fixtures for Threadline tests."""

from __future__ import annotations

import os
import pytest
from pathlib import Path


@pytest.fixture
def tmp_threadline_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Create an isolated Threadline home directory in a temp location.

    Sets THREADLINE_HOME env var so all threadline commands use this directory.
    Returns the path to the temp home directory.
    """
    home = tmp_path / ".threadline"
    home.mkdir(parents=True, exist_ok=True)

    # Set environment variable so threadline uses this directory
    monkeypatch.setenv("THREADLINE_HOME", str(home))

    return home


@pytest.fixture
def sample_markdown(tmp_path: Path) -> Path:
    """
    Create a sample markdown file with known content for testing.

    Returns the path to the created file.
    """
    content = """---
title: Test Journal Entry
date: 2024-01-15
---

# Morning Thoughts

Today I woke up feeling grateful for the simple things in life.
The sun was shining through my window, and I could hear birds singing outside.

This is a longer paragraph that contains multiple sentences. It should be chunked as a single entry. The content here is reflective and thoughtful, making it a good test case for classification.

## Todo List

- [ ] Buy groceries
- [ ] Call mom
- [ ] Finish the report

## Evening Reflection

Looking back on the day, I accomplished more than I expected.
There's something satisfying about crossing items off a todo list.

The key insight today was that small consistent actions compound over time.
"""

    md_file = tmp_path / "journal" / "2024-01-15.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(content)

    return md_file


@pytest.fixture
def sample_markdown_directory(tmp_path: Path) -> Path:
    """
    Create a directory with multiple markdown files for testing recursive ingestion.

    Returns the path to the directory containing the files.
    """
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories with files
    files = {
        "2024/january/entry1.md": """# January Entry 1

This is my first entry of January. I'm starting the year with renewed energy.

Setting intentions for the year ahead is important to me.
""",
        "2024/january/entry2.md": """# January Entry 2

Continuing my reflections from yesterday. Progress is being made.

Small steps lead to big changes over time.
""",
        "2024/february/entry1.md": """# February Entry

A new month brings new opportunities. Winter is slowly giving way to spring.

I'm grateful for the warmth of home during these cold days.
""",
        "notes/random.md": """# Random Notes

These are some random thoughts and observations.

- Idea one: explore new hobbies
- Idea two: read more books
- Idea three: exercise regularly
""",
    }

    for relative_path, content in files.items():
        file_path = journal_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    return journal_dir


@pytest.fixture
def initialized_threadline(tmp_threadline_home: Path) -> Path:
    """
    Return a tmp_threadline_home that has been initialized with threadline init.

    This fixture depends on tmp_threadline_home and runs init before returning.
    """
    from typer.testing import CliRunner
    from threadline.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["init"])

    # Verify initialization succeeded
    assert result.exit_code == 0, f"Init failed: {result.output}"

    return tmp_threadline_home
