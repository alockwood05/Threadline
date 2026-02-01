"""File scanning and hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator

from threadline.ingest.models import ScannedFile

# Supported file extensions
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".txt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".heic", ".webp"}


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_file_type(path: Path) -> str | None:
    """Detect file type from extension."""
    ext = path.suffix.lower()
    if ext in MARKDOWN_EXTENSIONS:
        return "markdown"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return None


def scan_path(path: Path) -> Iterator[ScannedFile]:
    """
    Scan a path for supported files.

    Args:
        path: A file or directory path

    Yields:
        ScannedFile objects for each supported file found
    """
    path = path.expanduser().resolve()

    if path.is_file():
        file_type = detect_file_type(path)
        if file_type:
            yield ScannedFile(
                path=path,
                filename=path.name,
                file_hash=compute_file_hash(path),
                file_type=file_type,
            )
    elif path.is_dir():
        # Recursively scan directory
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file():
                # Skip hidden files and directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                file_type = detect_file_type(file_path)
                if file_type:
                    yield ScannedFile(
                        path=file_path,
                        filename=file_path.name,
                        file_hash=compute_file_hash(file_path),
                        file_type=file_type,
                    )


def copy_to_originals(source: Path, originals_dir: Path, preserve_structure: bool = True) -> Path:
    """
    Copy a file to the originals directory.

    Args:
        source: Source file path
        originals_dir: Base originals directory
        preserve_structure: If True, preserve relative directory structure

    Returns:
        Path to the copied file (relative to originals_dir)
    """
    if preserve_structure:
        # Try to preserve some directory structure
        # Use the last 2 directory levels + filename
        parts = source.parts
        if len(parts) > 2:
            relative = Path(*parts[-3:])
        else:
            relative = Path(source.name)
    else:
        relative = Path(source.name)

    dest = originals_dir / relative

    # Handle name collisions
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.parent / f"{stem}_{counter}{suffix}"
            counter += 1

    # Create parent directories and copy
    dest.parent.mkdir(parents=True, exist_ok=True)

    import shutil
    shutil.copy2(source, dest)

    # Return path relative to originals_dir
    return relative
