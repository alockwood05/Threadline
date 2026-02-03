# Threadline - Product Requirements Document

A local-first journal entry management system for ingesting, indexing, browsing, and organizing personal writings.

## Problem Statement

Journal entries across multiple files (markdown, handwritten images) are siloed and hard to review. There's no unified way to:
- See all thoughts in one place
- Find connections between ideas
- Filter out noise (todo lists) from reflections
- Tag and revisit meaningful entries

## Goals

- Batch ingest journal files (markdown, images via OCR)
- Parse into discrete thought-units (entries)
- Preserve original content with links back to source
- Enable local-first browsing with infinite scroll TUI
- Support manual tagging and filtering
- Extract themes locally using embeddings (no external LLM required)
- Identify and filter todo lists vs reflective content

## Non-Goals (v1)

- Cloud sync
- Mobile app
- Real-time collaboration
- Full-text search (defer to Phase 2+)

---

## Local-First Philosophy

**Core principle:** Embeddings are the investment. Once generated, all analysis runs locally.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION (one-time)                        │
│   files → parse → chunk → classify → embed → store                 │
│                                                                     │
│   Can use LLM here for quality, OR run fully local                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DAILY USE (fully local)                        │
│   browse → filter → similarity search → theme exploration          │
│                                                                     │
│   All computed from stored embeddings - no network, no LLM         │
└─────────────────────────────────────────────────────────────────────┘
```

### Processing Modes

| Task | Local Option | LLM Option (optional) |
|------|--------------|----------------------|
| **Embeddings** | `nomic-embed-text-v1.5` or `bge-small-en-v1.5` | - |
| **Entry classification** | Zero-shot with `facebook/bart-large-mnli` | GPT-4o-mini / Claude |
| **Title generation** | First sentence + date (template) | LLM summary |
| **Summary quote** | First N chars / sentence extraction | LLM condensation |
| **Theme extraction** | BERTopic (HDBSCAN + c-TF-IDF) | - |
| **Similarity search** | Cosine distance on embeddings | - |
| **OCR** | `pytesseract` / `doctr` / `trocr` | Vision LLM |

**Recommended path:** Use local embeddings (`nomic-embed-text`), local classification (`bart-large-mnli`), and BERTopic for themes. LLM only needed if you want polished titles/summaries.

---

## Architecture

```
~/.threadline/
├── originals/           # Preserved source files (immutable)
├── threadline.db        # SQLite + sqlite-vss
├── models/              # Cached local models (embeddings, classifier)
└── config.yaml          # User preferences
```

### Tech Stack

| Component | Technology | Runs Locally |
|-----------|------------|--------------|
| Language | Python 3.11+ | Yes |
| Database | SQLite + sqlite-vss (vector search) | Yes |
| CLI | Typer | Yes |
| TUI | Textual | Yes |
| Embeddings | nomic-embed-text-v1.5 (384 dim) or bge-small-en-v1.5 (384 dim) | Yes |
| Classification | transformers + bart-large-mnli (zero-shot) | Yes |
| Theme extraction | BERTopic (UMAP + HDBSCAN + c-TF-IDF) | Yes |
| OCR | pytesseract, doctr, or trocr | Yes |
| LLM (optional) | Ollama (local) or OpenAI/Anthropic (remote) | Ollama: Yes |

### Local Model Sizes (for reference)

| Model | Size | RAM | Purpose |
|-------|------|-----|---------|
| `nomic-embed-text-v1.5` | ~130MB | ~500MB | Embeddings |
| `bge-small-en-v1.5` | ~130MB | ~500MB | Embeddings (alternative) |
| `bart-large-mnli` | ~1.6GB | ~2GB | Zero-shot classification |
| `trocr-base-handwritten` | ~330MB | ~1GB | Handwriting OCR |
| BERTopic dependencies | ~50MB | ~200MB | Theme extraction |

**Total footprint:** ~2-4GB RAM for full local operation.

### Data Model

```sql
-- Original source files
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,          -- path in originals/
    file_hash TEXT NOT NULL UNIQUE,  -- dedup
    file_type TEXT NOT NULL,         -- 'markdown', 'image'
    raw_text TEXT,                   -- OCR result or file content
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Individual thought-units parsed from sources
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    content TEXT NOT NULL,           -- the actual text
    title TEXT,                      -- "Date - description - location"
    entry_date DATE,                 -- extracted or inferred
    location TEXT,                   -- extracted if present
    entry_type TEXT,                 -- 'thought', 'todo', 'summary', 'list'
    entry_type_confidence REAL,      -- classifier confidence score
    summary_quote TEXT,              -- short preview for display
    embedding BLOB,                  -- vector for similarity (384 dim)
    source_line_start INTEGER,       -- reference back to original
    source_line_end INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tag definitions
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT,                      -- optional, for TUI display
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: entries <-> tags
CREATE TABLE entry_tags (
    entry_id INTEGER REFERENCES entries(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (entry_id, tag_id)
);

-- Extracted themes (from BERTopic, not user-created)
CREATE TABLE themes (
    id INTEGER PRIMARY KEY,
    topic_id INTEGER,                -- BERTopic's topic number
    name TEXT NOT NULL,              -- auto-generated or user-edited
    keywords TEXT,                   -- JSON array of top terms with weights
    representative_docs TEXT,        -- JSON array of example entry IDs
    entry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE entry_themes (
    entry_id INTEGER REFERENCES entries(id),
    theme_id INTEGER REFERENCES themes(id),
    probability REAL,                -- BERTopic probability score
    PRIMARY KEY (entry_id, theme_id)
);

-- Model metadata (track which models produced what)
CREATE TABLE model_runs (
    id INTEGER PRIMARY KEY,
    run_type TEXT NOT NULL,          -- 'embedding', 'classification', 'themes'
    model_name TEXT NOT NULL,
    model_version TEXT,
    entries_processed INTEGER,
    run_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Features & Acceptance Criteria

### Phase 1: Ingestion & Storage

#### F1.1: Batch File Import
Import multiple files in a single command.

- [x] `threadline ingest <path>` accepts a file or directory
- [x] Recursively finds `.md` and image files (`.png`, `.jpg`, `.jpeg`, `.heic`)
- [x] Skips already-imported files (by hash)
- [x] Copies originals to `~/.threadline/originals/` preserving directory structure
- [x] Shows progress bar for batch operations
- [x] Outputs summary: X files imported, Y skipped (duplicates), Z failed

#### F1.2: OCR for Images *(local)*
Extract text from handwritten/typed journal images.

- [x] Detects image files during ingestion
- [x] Default: `pytesseract` for typed text
- [x] Option: `--ocr=trocr` for handwritten text (uses `trocr-base-handwritten`)
- [ ] Option: `--ocr=vision` for LLM-based OCR (requires LLM config)
- [x] Stores raw OCR text in `sources.raw_text`
- [x] Handles OCR failures gracefully (logs error, continues batch)

#### F1.3: Markdown Parsing *(local)*
Parse markdown files preserving structure.

- [x] Reads markdown content into `sources.raw_text`
- [x] Preserves frontmatter if present (extracts date, location, title)
- [x] Handles UTF-8 encoding

#### F1.4: Entry Chunking *(local)*
Split source content into discrete entries (thought-units).

- [x] Splits on paragraph boundaries (double newline)
- [x] Each chunk becomes one `entries` row
- [x] Links entry to source via `source_id`
- [x] Records `source_line_start` and `source_line_end` for traceability
- [x] Minimum chunk size threshold (skip empty paragraphs)
- [x] Configurable: `--min-chunk-chars=50`

#### F1.5: Entry Classification *(local or LLM)*
Classify each entry's type.

**Local mode (default):**
- [x] Uses `facebook/bart-large-mnli` for zero-shot classification
- [x] Candidate labels: `thought`, `todo list`, `summary`, `bullet list`, `prayer`, `reflection`, `question`
- [x] Stores result in `entries.entry_type`
- [x] Stores confidence in `entries.entry_type_confidence`
- [x] Runs on CPU (GPU optional for speed)

**LLM mode (`--classifier=llm`):**
- [ ] Sends entries to configured LLM
- [ ] More nuanced classification possible
- [ ] Batch API calls to minimize latency

**Both modes:**
- [ ] `--reclassify` flag to re-run on existing entries
- [ ] Low-confidence entries flagged for manual review

#### F1.6: Title Generation *(local or LLM)*
Auto-generate descriptive titles for entries.

**Local mode (default):**
- [x] Format: `YYYY-MM-DD - <first_sentence_truncated>`
- [x] Date: extract from content → filename → file modified date
- [x] Uses `dateparser` library for flexible date extraction
- [ ] Location: extract via simple patterns ("in Portland", "at home")

**LLM mode (`--titles=llm`):**
- [ ] Format: `YYYY-MM-DD - <llm_summary> - <location>`
- [ ] LLM generates 3-5 word description
- [ ] Store in `entries.title`

#### F1.7: Summary Quote Generation *(local)*
Create preview text for each entry.

- [x] Short entries (<100 chars): use full content
- [x] Long entries: extract first sentence or first 100 chars + "..."
- [x] Store in `entries.summary_quote`
- [ ] Optional: `--summaries=llm` for LLM-generated condensations

#### F1.8: Embedding Generation *(local)*
Generate vector embeddings for similarity search.

- [x] Default model: `nomic-embed-text-v1.5` (384 dimensions, excellent quality) *(currently using all-MiniLM-L6-v2)*
- [ ] Alternative: `bge-small-en-v1.5` (384 dimensions)
- [x] Runs locally on CPU (no API, no GPU required)
- [x] Downloads model on first run, caches in `~/.threadline/models/`
- [x] Store embedding as BLOB in `entries.embedding`
- [x] Create sqlite-vss index for fast similarity queries
- [ ] Records model info in `model_runs` table

#### F1.9: Database Initialization *(local)*
Set up SQLite database on first run.

- [x] `threadline init` creates `~/.threadline/` structure
- [x] Creates SQLite database with schema
- [x] Initializes sqlite-vss extension
- [x] Creates `originals/` and `models/` directories
- [x] Generates default `config.yaml`
- [ ] Downloads default embedding model *(lazy loaded on first ingest)*

#### F1.10: Regression Tests
Minimal, pragmatic tests to verify CLI commands work correctly.

**Scope:**
- Test each CLI command's core functionality
- Use temp directories to avoid polluting user data
- Fast execution (< 30 seconds for full suite)
- Run with `pytest tests/` or `threadline test` (if added)

**Test Coverage:**
- [x] `test_init`: `threadline init` creates expected directory structure and files
- [x] `test_ingest_markdown`: `threadline ingest` successfully imports a markdown file, creates source and entry records
- [x] `test_ingest_skip_duplicates`: Re-ingesting same file skips it (by hash)
- [x] `test_ingest_directory`: `threadline ingest <dir>` recursively finds and imports files
- [x] `test_stats`: `threadline stats` returns valid counts matching database state
- [x] `test_entry_has_embedding`: Ingested entries have non-null embeddings
- [x] `test_entry_has_classification`: Ingested entries have entry_type and confidence
- [x] `test_image_file_detected_during_scan`: Image files detected with correct file_type
- [x] `test_image_ingest_graceful_failure_without_ocr`: OCR failures handled gracefully
- [x] `test_ocr_flag_accepted`: `--ocr` CLI flag recognized

**Test Fixtures:**
- [x] `tmp_threadline_home`: Creates isolated `~/.threadline` equivalent in temp dir
- [x] `sample_markdown`: Sample markdown file with known content for predictable testing

---

### Phase 2: Browsing (TUI) *(fully local)*

#### F2.1: Entry List View
Infinite scroll list of all entries.

- [x] Launch with `threadline browse`
- [x] Shows entries in reverse chronological order (newest first)
- [x] Each row displays: `title` | `summary_quote` | `entry_type` badge
- [x] Color-coded badges by entry_type
- [x] Lazy loading: fetches entries in pages as user scrolls
- [x] Keyboard navigation: `j/k` or arrow keys to move
- [x] `Enter` to expand/view full entry
- [x] `q` to quit

#### F2.2: Entry Detail View
View full entry content with metadata.

- [x] Shows full `content` text
- [x] Displays: title, date, location, entry_type, tags
- [x] Shows classification confidence (if <0.7, shows "uncertain")
- [x] Shows link to original source file
- [x] `o` to open original file in `$EDITOR`
- [x] `Esc` or `q` to return to list

#### F2.3: Quick Tagging
Tag entries without leaving list view.

- [x] `t` opens tag picker overlay
- [x] Shows existing tags with checkbox (toggle on/off)
- [x] Type to filter/search tags
- [x] `n` to create new tag inline
- [x] Changes save immediately
- [x] Visual indicator on list row if entry has tags

#### F2.4: Filtering
Filter entries by type and tags.

- [x] `f` opens filter panel
- [x] Filter by `entry_type` (checkboxes: thought, todo, summary, etc.)
- [x] Filter by tags (multi-select)
- [x] "Hide todos" quick toggle (common use case)
- [x] Active filters shown in status bar
- [x] `c` to clear all filters
- [x] Filters persist during session

#### F2.5: Theme Overview
Display algorithmically-extracted themes.

- [x] `Shift+T` opens themes panel
- [x] Lists themes with entry count
- [x] Shows top 5 keywords per theme
- [x] Select theme to filter entries by that theme
- [x] Themes generated by BERTopic (see F3.1)

---

### Phase 3: Theme Extraction & Search *(fully local)*

#### F3.1: Local Theme Extraction with BERTopic
Extract themes using embeddings - no LLM required.

- [x] `threadline extract-themes` runs extraction
- [x] Pipeline: stored embeddings → UMAP (dimensionality reduction) → HDBSCAN (clustering) → c-TF-IDF (keywords)
- [x] Automatically determines optimal number of themes (no manual count needed)
- [x] Option: `--min-topic-size=10` to control granularity
- [x] Stores results in `themes` and `entry_themes` tables
- [x] Saves representative documents per theme
- [x] Re-runnable (clears and regenerates)
- [x] Completes in <30 seconds for 1000 entries on CPU
- [x] Records run metadata in `model_runs`

#### F3.2: Similarity Search *(local)*
Find similar entries using embeddings.

- [x] `s` in detail view shows similar entries
- [x] Uses cosine similarity on embeddings
- [x] Returns top 10 similar entries with similarity scores
- [x] Navigate to any similar entry
- [x] Also available via CLI: `threadline similar <entry_id>`

#### F3.3: Tag Management CLI
Manage tags from command line.

- [ ] `threadline tags list` - show all tags with counts
- [ ] `threadline tags create <name>` - create new tag
- [ ] `threadline tags delete <name>` - delete tag (with confirmation)
- [ ] `threadline tags rename <old> <new>` - rename tag
- [ ] `threadline tags merge <source> <target>` - merge tags

---

### Phase 4: Export & Maintenance

#### F4.1: Export Filtered Entries
Export entries matching filters.

- [ ] `threadline export --filter-type=thought --tag=important -o output.md`
- [ ] Formats as markdown with headers per entry
- [ ] Includes metadata (date, source link, tags)
- [ ] Option: `--format=json` for structured export
- [ ] Option: `--include-similar` to include related entries

#### F4.2: Re-process Entries
Re-run processing on existing entries.

- [ ] `threadline reprocess --embeddings` - regenerate with different model
- [ ] `threadline reprocess --classify` - re-run classification
- [ ] `threadline reprocess --themes` - alias for `extract-themes`
- [ ] Useful after model upgrades or config changes
- [ ] Shows before/after comparison for classification changes

#### F4.3: Database Backup
Backup and restore functionality.

- [ ] `threadline backup` - creates timestamped backup of db + originals
- [ ] `threadline restore <backup>` - restores from backup
- [ ] Backup location configurable
- [ ] Automatic backup before destructive operations

#### F4.4: Statistics & Health
View system status.

- [ ] `threadline stats` - show counts (sources, entries, tags, themes)
- [ ] Shows embedding model info and coverage
- [ ] Shows classification distribution
- [ ] `threadline doctor` - check for issues (missing embeddings, orphaned entries)

---


## Phase 5: Code Quality & Performance

Technical debt cleanup and performance optimizations identified through architectural review.

### F5.1: Database Connection Standardization
Standardize database connection handling across all CLI commands.

- [ ] Use `get_db()` context manager consistently in all commands
- [ ] Remove manual `Database()` instantiation and `close()` calls
- [ ] Add connection error handling with user-friendly messages

### F5.2: Batch Insert Optimization
Improve database write performance for large ingestions.

- [ ] Replace `create_many()` loop with `executemany()` for single commit
- [ ] Add transaction support with rollback on failure
- [ ] Target: 10x improvement for 100+ entry batches

### F5.3: Vector Similarity Search Optimization
Use sqlite-vss extension for database-side similarity search.

- [ ] Implement `find_similar()` using VSS virtual table instead of Python-side calculation
- [ ] Remove full table scan for similarity queries
- [ ] Target: <100ms for similarity search regardless of entry count

### F5.4: TUI Code Modularization
Split monolithic TUI app into focused modules.

- [ ] Extract `screens/browse.py` - Browse screen logic
- [ ] Extract `widgets/entry_card.py` - Entry display widgets
- [ ] Extract `widgets/tag_picker.py` - Tag picker widget
- [ ] Extract `widgets/filter_panel.py` - Filter controls
- [ ] Create base `ToggleWidget` class to reduce checkbox duplication

### F5.5: Type Annotation Consistency
Standardize Python type annotations across codebase.

- [ ] Add `from __future__ import annotations` to all modules
- [ ] Ensure all public functions have return type hints
- [ ] Add missing parameter type hints

### F5.6: Error Handling Improvements
Improve error handling and logging throughout.

- [ ] Replace silent `except: pass` with logged warnings
- [ ] Add custom exception classes for repository errors
- [ ] Add `--verbose` flag for detailed error output

---

## Configuration

`~/.threadline/config.yaml`:

```yaml
# Processing mode: 'local' (default) or 'hybrid' (local + LLM for titles/summaries)
mode: local

# Embedding settings (always local)
embeddings:
  model: nomic-embed-text-v1.5    # or bge-small-en-v1.5
  # model: BAAI/bge-small-en-v1.5  # alternative

# Classification settings
classification:
  method: local                    # 'local' or 'llm'
  model: facebook/bart-large-mnli  # for local zero-shot
  labels:                          # customizable categories
    - thought
    - todo list
    - summary
    - bullet list
    - prayer
    - reflection
    - question
  confidence_threshold: 0.6        # below this, mark as 'uncertain'

# Title generation
titles:
  method: local                    # 'local' or 'llm'
  # local uses: date + first sentence

# OCR settings
ocr:
  default: pytesseract             # pytesseract, doctr, trocr, vision
  handwriting: trocr               # model for --ocr=handwriting

# Theme extraction (BERTopic)
themes:
  min_topic_size: 5                # minimum entries per theme
  nr_topics: auto                  # 'auto' or specific number

# LLM settings (only used if method: llm anywhere above)
llm:
  provider: ollama                 # ollama, openai, anthropic
  model: llama3.2                  # model name
  # For remote providers:
  # api_key_env: OPENAI_API_KEY

# TUI settings
tui:
  page_size: 50
  date_format: "%Y-%m-%d"
  theme: dark                      # dark, light

# Storage
storage:
  path: ~/.threadline              # base directory
  backup_path: ~/.threadline/backups
```

---

## CLI Commands Summary

```
threadline init                    # Initialize ~/.threadline
threadline ingest <path>           # Import files (local processing)
  --ocr=pytesseract|trocr|vision   # OCR method
  --classifier=local|llm           # Classification method
  --titles=local|llm               # Title generation method

threadline browse                  # Open TUI browser

threadline tags list|create|delete|rename|merge

threadline extract-themes          # Run BERTopic theme extraction
  --min-topic-size=N               # Minimum entries per theme

threadline similar <entry_id>      # Find similar entries

threadline export [options]        # Export entries
  --filter-type=<type>
  --tag=<tag>
  --format=md|json

threadline reprocess               # Re-run processing
  --embeddings                     # Regenerate embeddings
  --classify                       # Re-run classification
  --themes                         # Re-extract themes

threadline backup                  # Backup database
threadline restore <backup>        # Restore from backup
threadline stats                   # Show statistics
threadline doctor                  # Check for issues
```

---

## Success Metrics

- Ingest 100+ journal files without manual intervention
- Full local processing (no network) after initial model download
- Browse all entries in <2 seconds initial load
- Tag an entry in <3 keystrokes
- Theme extraction completes in <30 seconds for 1000 entries
- Similarity search returns in <100ms
- Total disk footprint <5GB (including models)
- RAM usage <4GB during processing
- Zero data loss (originals always preserved)

---

## Implementation Order

### MVP (Phase 1a)
1. F1.9: Database initialization
2. F1.1: Batch file import (markdown only)
3. F1.3: Markdown parsing
4. F1.4: Entry chunking
5. F1.8: Embedding generation

**Outcome:** Can ingest markdown files and store with embeddings.

### Phase 1b
6. F1.5: Entry classification (local)
7. F1.6: Title generation (local)
8. F1.7: Summary quote generation
9. F1.2: OCR for images

**Outcome:** Full ingestion pipeline working locally.

### Phase 2
10. F2.1: Entry list view (TUI)
11. F2.2: Entry detail view
12. F2.3: Quick tagging
13. F2.4: Filtering
14. F3.3: Tag management CLI

**Outcome:** Can browse and tag entries.

### Phase 3
15. F3.1: Theme extraction (BERTopic)
16. F3.2: Similarity search
17. F2.5: Theme overview in TUI

**Outcome:** Full local analysis capabilities.

### Phase 4
18. F4.1: Export
19. F4.2: Reprocess
20. F4.3: Backup/restore
21. F4.4: Stats/doctor

**Outcome:** Production-ready maintenance tools.

### Phase 5
22. F5.1: Database connection standardization
23. F5.2: Batch insert optimization
24. F5.3: Vector similarity search optimization
25. F5.4: TUI code modularization
26. F5.5: Type annotation consistency
27. F5.6: Error handling improvements

**Outcome:** Cleaner, faster, more maintainable codebase.

---

## Open Questions

1. **Chunk granularity** - Paragraph boundaries work for prose. May need special handling for bullet lists (treat list as one entry vs each bullet as entry). Could use classification confidence to flag for manual review.

2. **Entry type taxonomy** - Current list: thought, todo list, summary, bullet list, prayer, reflection, question. Add/remove based on actual journal content.

3. **Location extraction** - Start with simple regex patterns ("in Portland", "at home", "from the office"). Could upgrade to NER model later if needed.

4. **Handwriting OCR quality** - `trocr` works well for clean handwriting. May need to evaluate quality on your specific handwriting style.

5. **Theme naming** - BERTopic generates keyword lists. Could add optional LLM pass to generate human-readable theme names, or just use top keyword.
