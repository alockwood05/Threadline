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


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """
    Create a simple test image file for OCR testing.

    Returns the path to the created image file.
    """
    # Create a minimal valid PNG file (1x1 pixel, white)
    # PNG file format: signature + IHDR chunk + IDAT chunk + IEND chunk
    png_data = bytes([
        # PNG signature
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        # IHDR chunk (width=1, height=1, bit_depth=8, color_type=2 RGB)
        0x00, 0x00, 0x00, 0x0D,  # chunk length
        0x49, 0x48, 0x44, 0x52,  # IHDR
        0x00, 0x00, 0x00, 0x01,  # width
        0x00, 0x00, 0x00, 0x01,  # height
        0x08, 0x02,              # bit depth, color type
        0x00, 0x00, 0x00,        # compression, filter, interlace
        0x90, 0x77, 0x53, 0xDE,  # CRC
        # IDAT chunk (compressed pixel data for 1 white pixel)
        0x00, 0x00, 0x00, 0x0C,  # chunk length
        0x49, 0x44, 0x41, 0x54,  # IDAT
        0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF, 0x00,
        0x05, 0xFE, 0x02, 0xFE,  # CRC placeholder (not strictly valid but works)
        # IEND chunk
        0x00, 0x00, 0x00, 0x00,  # chunk length
        0x49, 0x45, 0x4E, 0x44,  # IEND
        0xAE, 0x42, 0x60, 0x82,  # CRC
    ])

    img_file = tmp_path / "test_image.png"
    img_file.write_bytes(png_data)

    return img_file
