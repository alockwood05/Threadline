"""Data access repositories."""

from threadline.db.repositories.sources import SourceRepository
from threadline.db.repositories.entries import EntryRepository

__all__ = ["SourceRepository", "EntryRepository"]
