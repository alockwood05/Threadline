# Threadline

A local-first journal entry management system for ingesting, indexing, browsing, and organizing personal writings.

## Features

- **Batch ingest** markdown files and images (OCR)
- **Parse into entries** - split documents into discrete thought-units
- **Local embeddings** - generate semantic embeddings for similarity search
- **Theme extraction** - discover patterns using BERTopic (no LLM required)
- **TUI browser** - infinite scroll interface for reviewing entries
- **Tagging & filtering** - organize and find relevant entries

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize Threadline
threadline init

# Import journal files
threadline ingest ~/journals/

# View statistics
threadline stats

# Browse entries (coming in Phase 2)
threadline browse
```

## Development Status

**MVP (Phase 1a) - Complete:**
- Database initialization
- Batch file import (markdown)
- Entry chunking
- Embedding generation

**Phase 1b - Planned:**
- Entry classification
- Title generation (LLM-assisted)
- OCR for images

**Phase 2 - Planned:**
- TUI browser
- Tagging
- Filtering

**Phase 3 - Planned:**
- Theme extraction (BERTopic)
- Similarity search

See [PRD.md](PRD.md) for full feature breakdown and [ARCHITECTURE.md](ARCHITECTURE.md) for technical design.

## License

MIT
