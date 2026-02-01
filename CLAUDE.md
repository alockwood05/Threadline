# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Threadline is a local-first journal entry management system for ingesting, indexing, and organizing personal writings. It parses markdown files into discrete "thought-units" (entries), generates embeddings for similarity search, and classifies entry types using local ML models.

**Key principle:** Embeddings are the investment. Once generated during ingestion, all analysis runs locally with no network or LLM required.

## Commands

```bash
# Install in development mode
pip install -e .

# Run CLI
threadline init                    # Initialize ~/.threadline
threadline ingest <path>           # Import markdown files
threadline stats                   # Show database statistics

# Run tests
pytest tests/                      # All tests
pytest tests/ -m "not slow"        # Skip slow ML model tests
pytest tests/test_cli.py::TestInit # Single test class

# Linting
ruff check src/
ruff format src/
mypy src/
```

## Architecture

### Directory Layout

```
src/threadline/
├── cli/          # Typer CLI commands (thin layer, delegates to core/db)
├── core/         # Business logic (chunker, classifier, embedder) - no I/O
├── ingest/       # Ingestion pipeline orchestration
├── db/           # SQLite + sqlite-vss, repository pattern
│   └── repositories/  # CRUD operations per table
├── models/       # ML model wrappers (lazy-loaded)
└── config/       # Pydantic settings, path resolution
```

### Data Flow

1. `cli/ingest.py` → receives path, shows progress
2. `ingest/pipeline.py` → orchestrates: scan → parse → chunk → classify → embed → store
3. `core/` modules process data (pure functions, no side effects)
4. `db/repositories/` handle all database operations

### Key Design Patterns

- **Repository pattern**: All SQL is in `db/repositories/`, not scattered in business logic
- **Lazy model loading**: ML models (~2GB) only load on first use
- **Pydantic models**: Type-safe data contracts between layers (`ingest/models.py`)

### Database

SQLite with sqlite-vss extension for vector similarity search. Tables:
- `sources`: imported files with file hash for dedup
- `entries`: chunked content with embeddings (384-dim BLOB), classification, titles
- `tags`, `entry_tags`: user-defined labels (Phase 2)
- `themes`, `entry_themes`: auto-extracted topics via BERTopic (Phase 3)

## Testing

Tests use `THREADLINE_HOME` env var to isolate from real `~/.threadline/`.

Key fixtures in `tests/conftest.py`:
- `tmp_threadline_home`: isolated temp directory
- `initialized_threadline`: temp home with `threadline init` already run
- `sample_markdown`: test file with known content

Tests marked `@pytest.mark.slow` require ML model loading.

## Development Status

- **Phase 1a (Complete)**: init, ingest markdown, chunking, embeddings
- **Phase 1b (Complete)**: entry classification, title/summary generation
- **Phase 2 (Planned)**: TUI browser with Textual
- **Phase 3 (Planned)**: BERTopic theme extraction, similarity search

See `PRD.md` for acceptance criteria checkboxes and `ARCHITECTURE.md` for detailed design.

## Automated Development

The `ralph-prompt.md` file contains instructions for automated feature development cycles. It guides implementing one feature at a time, verifying acceptance criteria, and updating PRD checkboxes.
