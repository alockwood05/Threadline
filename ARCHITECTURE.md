# Threadline - Architecture

## Project Structure

```
threadline/
├── pyproject.toml              # Project metadata, dependencies, entry points
├── README.md                   # Quick start guide
├── PRD.md                      # Product requirements
├── ARCHITECTURE.md             # This file
│
├── src/
│   └── threadline/
│       ├── __init__.py         # Package version, exports
│       ├── __main__.py         # Entry point: python -m threadline
│       │
│       ├── cli/                # Command-line interface (Typer)
│       │   ├── __init__.py
│       │   ├── main.py         # Root CLI app, command registration
│       │   ├── ingest.py       # threadline ingest <path>
│       │   ├── browse.py       # threadline browse (launches TUI)
│       │   ├── tags.py         # threadline tags list|create|delete|rename|merge
│       │   ├── themes.py       # threadline extract-themes
│       │   ├── export.py       # threadline export
│       │   ├── maintenance.py  # threadline backup|restore|stats|doctor|reprocess
│       │   └── init.py         # threadline init
│       │
│       ├── core/               # Core business logic (no I/O)
│       │   ├── __init__.py
│       │   ├── chunker.py      # Split text into entries (paragraph boundaries)
│       │   ├── classifier.py   # Entry type classification (local/LLM)
│       │   ├── embedder.py     # Generate embeddings (sentence-transformers)
│       │   ├── theme_extractor.py  # BERTopic wrapper
│       │   ├── title_generator.py  # Title/summary generation
│       │   ├── date_extractor.py   # Date parsing from content/filename
│       │   └── similarity.py   # Cosine similarity search
│       │
│       ├── ingest/             # File ingestion pipeline
│       │   ├── __init__.py
│       │   ├── pipeline.py     # Orchestrates full ingestion flow
│       │   ├── file_scanner.py # Find files, compute hashes, detect types
│       │   ├── markdown.py     # Parse markdown, extract frontmatter
│       │   ├── ocr.py          # OCR handlers (pytesseract, trocr, vision)
│       │   └── models.py       # Pydantic models for ingestion data
│       │
│       ├── db/                 # Database layer
│       │   ├── __init__.py
│       │   ├── connection.py   # SQLite connection, sqlite-vss setup
│       │   ├── schema.py       # Table definitions, migrations
│       │   ├── repositories/   # Data access objects
│       │   │   ├── __init__.py
│       │   │   ├── sources.py  # CRUD for sources table
│       │   │   ├── entries.py  # CRUD for entries table
│       │   │   ├── tags.py     # CRUD for tags, entry_tags
│       │   │   └── themes.py   # CRUD for themes, entry_themes
│       │   └── queries.py      # Complex queries (filtered lists, similarity)
│       │
│       ├── tui/                # Terminal UI (Textual)
│       │   ├── __init__.py
│       │   ├── app.py          # Main Textual App
│       │   ├── screens/
│       │   │   ├── __init__.py
│       │   │   ├── browse.py   # Entry list view (infinite scroll)
│       │   │   ├── detail.py   # Entry detail view
│       │   │   └── themes.py   # Theme overview screen
│       │   ├── widgets/
│       │   │   ├── __init__.py
│       │   │   ├── entry_list.py   # Scrollable entry list widget
│       │   │   ├── entry_card.py   # Single entry display
│       │   │   ├── tag_picker.py   # Tag selection overlay
│       │   │   ├── filter_panel.py # Filter controls
│       │   │   └── status_bar.py   # Active filters, stats
│       │   └── styles.tcss     # Textual CSS styling
│       │
│       ├── models/             # ML model management
│       │   ├── __init__.py
│       │   ├── loader.py       # Download/cache models
│       │   ├── embedding.py    # Embedding model wrapper
│       │   ├── classifier.py   # Zero-shot classifier wrapper
│       │   └── ocr.py          # OCR model wrappers
│       │
│       ├── llm/                # Optional LLM integration
│       │   ├── __init__.py
│       │   ├── client.py       # Unified LLM client (ollama/openai/anthropic)
│       │   ├── prompts.py      # Prompt templates
│       │   └── batch.py        # Batch processing utilities
│       │
│       └── config/             # Configuration management
│           ├── __init__.py
│           ├── settings.py     # Pydantic settings from config.yaml
│           ├── paths.py        # Path resolution (~/.threadline/*)
│           └── defaults.py     # Default configuration values
│
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── test_cli/
│   ├── test_core/
│   ├── test_db/
│   ├── test_ingest/
│   └── test_tui/
│
└── scripts/
    ├── setup_dev.sh            # Dev environment setup
    └── download_models.py      # Pre-download models for offline use
```

---

## Module Responsibilities

### `cli/` - Command Line Interface

Thin layer using Typer. Each file maps to a command group. Handles:
- Argument parsing
- Progress bars (rich)
- Error display
- Delegates to core/db/ingest modules

```python
# cli/main.py
import typer
from threadline.cli import ingest, browse, tags, themes, export, maintenance, init

app = typer.Typer(name="threadline", help="Journal entry management")

app.add_typer(tags.app, name="tags")
app.command()(init.init_cmd)
app.command()(ingest.ingest_cmd)
app.command()(browse.browse_cmd)
app.command()(themes.extract_themes_cmd)
app.command()(export.export_cmd)
# ... etc
```

### `core/` - Business Logic

Pure functions, no side effects. Easy to test.

```python
# core/chunker.py
def chunk_text(text: str, min_chars: int = 50) -> list[Chunk]:
    """Split text into paragraph chunks with line numbers."""
    ...

# core/classifier.py
class EntryClassifier:
    def __init__(self, model_name: str, labels: list[str]): ...
    def classify(self, text: str) -> tuple[str, float]: ...  # (label, confidence)
    def classify_batch(self, texts: list[str]) -> list[tuple[str, float]]: ...

# core/embedder.py
class Embedder:
    def __init__(self, model_name: str): ...
    def embed(self, text: str) -> np.ndarray: ...
    def embed_batch(self, texts: list[str]) -> np.ndarray: ...
```

### `ingest/` - Ingestion Pipeline

Orchestrates the full import flow.

```python
# ingest/pipeline.py
class IngestPipeline:
    def __init__(
        self,
        db: Database,
        embedder: Embedder,
        classifier: EntryClassifier,
        config: IngestConfig,
    ): ...

    def ingest_path(self, path: Path) -> IngestResult:
        """
        1. Scan for files
        2. Filter duplicates (by hash)
        3. Copy to originals/
        4. Parse content (markdown or OCR)
        5. Chunk into entries
        6. Classify entries
        7. Generate titles/summaries
        8. Generate embeddings
        9. Store in database
        """
        ...
```

### `db/` - Data Access

Repository pattern for clean separation.

```python
# db/repositories/entries.py
class EntryRepository:
    def __init__(self, conn: sqlite3.Connection): ...

    def create(self, entry: EntryCreate) -> int: ...
    def get(self, entry_id: int) -> Entry | None: ...
    def list(
        self,
        offset: int = 0,
        limit: int = 50,
        entry_types: list[str] | None = None,
        tag_ids: list[int] | None = None,
        theme_id: int | None = None,
    ) -> list[Entry]: ...
    def update_tags(self, entry_id: int, tag_ids: list[int]) -> None: ...
    def find_similar(self, embedding: bytes, limit: int = 10) -> list[tuple[Entry, float]]: ...
```

### `tui/` - Terminal Interface

Textual-based TUI with screens and widgets.

```python
# tui/app.py
from textual.app import App
from threadline.tui.screens import BrowseScreen, DetailScreen, ThemesScreen

class ThreadlineApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "toggle_filter", "Filter"),
        ("t", "tag", "Tag"),
    ]

    def on_mount(self) -> None:
        self.push_screen(BrowseScreen())
```

### `models/` - ML Model Management

Handles model download, caching, and loading.

```python
# models/loader.py
from pathlib import Path
from huggingface_hub import hf_hub_download

MODELS_DIR = Path("~/.threadline/models").expanduser()

def ensure_model(model_name: str) -> Path:
    """Download model if not cached, return local path."""
    ...

# models/embedding.py
from sentence_transformers import SentenceTransformer

class EmbeddingModel:
    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        self.model = SentenceTransformer(model_name, cache_folder=MODELS_DIR)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True)
```

### `config/` - Configuration

Pydantic settings with YAML loading.

```python
# config/settings.py
from pydantic import BaseModel
from pathlib import Path
import yaml

class EmbeddingConfig(BaseModel):
    model: str = "nomic-ai/nomic-embed-text-v1.5"

class ClassificationConfig(BaseModel):
    method: str = "local"  # local | llm
    model: str = "facebook/bart-large-mnli"
    labels: list[str] = ["thought", "todo list", "summary", "bullet list", "prayer", "reflection", "question"]
    confidence_threshold: float = 0.6

class Settings(BaseModel):
    mode: str = "local"
    embeddings: EmbeddingConfig = EmbeddingConfig()
    classification: ClassificationConfig = ClassificationConfig()
    # ... etc

def load_settings(config_path: Path | None = None) -> Settings:
    if config_path is None:
        config_path = Path("~/.threadline/config.yaml").expanduser()
    if config_path.exists():
        with open(config_path) as f:
            return Settings(**yaml.safe_load(f))
    return Settings()
```

---

## Data Flow

### Ingestion Flow

```
User: threadline ingest ~/journals/

┌─────────────────────────────────────────────────────────────────────┐
│ cli/ingest.py                                                       │
│   - Parse args                                                      │
│   - Initialize pipeline with config                                 │
│   - Show progress bar                                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ingest/pipeline.py                                                  │
│                                                                     │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │ file_scanner │───▶│ markdown.py  │───▶│ chunker.py   │         │
│   │              │    │ ocr.py       │    │              │         │
│   └──────────────┘    └──────────────┘    └──────────────┘         │
│          │                   │                   │                  │
│          ▼                   ▼                   ▼                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │ sources repo │    │ raw_text     │    │ entries      │         │
│   └──────────────┘    └──────────────┘    └──────────────┘         │
│                                                  │                  │
│   ┌──────────────────────────────────────────────┘                 │
│   │                                                                 │
│   ▼                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │ classifier   │───▶│ title_gen    │───▶│ embedder     │         │
│   └──────────────┘    └──────────────┘    └──────────────┘         │
│          │                   │                   │                  │
│          ▼                   ▼                   ▼                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │ entry_type   │    │ title        │    │ embedding    │         │
│   │ confidence   │    │ summary_quote│    │ (BLOB)       │         │
│   └──────────────┘    └──────────────┘    └──────────────┘         │
│                                                                     │
│   All stored via db/repositories/entries.py                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Browse Flow

```
User: threadline browse

┌─────────────────────────────────────────────────────────────────────┐
│ cli/browse.py                                                       │
│   - Launch Textual app                                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ tui/app.py                                                          │
│   - Mount BrowseScreen                                              │
│   - Handle global keybindings                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ tui/screens/browse.py                                               │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │ StatusBar (active filters, entry count)                     │  │
│   ├─────────────────────────────────────────────────────────────┤  │
│   │                                                             │  │
│   │  EntryList (infinite scroll)                                │  │
│   │    ├── EntryCard (title | quote | type badge)               │  │
│   │    ├── EntryCard                                            │  │
│   │    ├── EntryCard                                            │  │
│   │    └── ... (lazy loaded)                                    │  │
│   │                                                             │  │
│   ├─────────────────────────────────────────────────────────────┤  │
│   │ [j/k] Navigate  [Enter] View  [t] Tag  [f] Filter  [q] Quit │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   On scroll: entries_repo.list(offset=N, limit=50, filters=...)    │
│   On Enter: push_screen(DetailScreen(entry_id))                    │
│   On t: show overlay(TagPicker)                                    │
│   On f: show overlay(FilterPanel)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Theme Extraction Flow

```
User: threadline extract-themes

┌─────────────────────────────────────────────────────────────────────┐
│ cli/themes.py                                                       │
│   - Load all entries with embeddings                                │
│   - Run ThemeExtractor                                              │
│   - Store results                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ core/theme_extractor.py                                             │
│                                                                     │
│   embeddings (N x 384)                                              │
│         │                                                           │
│         ▼                                                           │
│   ┌──────────────┐                                                  │
│   │ UMAP         │  Reduce 384 → 5 dimensions                       │
│   └──────────────┘                                                  │
│         │                                                           │
│         ▼                                                           │
│   ┌──────────────┐                                                  │
│   │ HDBSCAN      │  Cluster into topics (auto-detects count)        │
│   └──────────────┘                                                  │
│         │                                                           │
│         ▼                                                           │
│   ┌──────────────┐                                                  │
│   │ c-TF-IDF     │  Extract keywords per topic                      │
│   └──────────────┘                                                  │
│         │                                                           │
│         ▼                                                           │
│   ThemeResult:                                                      │
│     - topics: list[Topic]                                           │
│         - id, keywords, representative_doc_ids                      │
│     - assignments: dict[entry_id, (topic_id, probability)]          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "threadline"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # CLI
    "typer>=0.9.0",
    "rich>=13.0.0",

    # TUI
    "textual>=0.47.0",

    # Database
    "sqlite-vss>=0.1.2",

    # ML - Embeddings
    "sentence-transformers>=2.2.0",
    "torch>=2.0.0",           # CPU-only build recommended

    # ML - Classification
    "transformers>=4.36.0",

    # ML - Theme extraction
    "bertopic>=0.16.0",
    "umap-learn>=0.5.0",
    "hdbscan>=0.8.0",

    # OCR
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",

    # Parsing
    "python-frontmatter>=1.0.0",
    "dateparser>=1.2.0",

    # Config
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
# Handwriting OCR
ocr-handwriting = [
    "transformers>=4.36.0",  # for trocr
]

# LLM integrations
llm = [
    "openai>=1.0.0",
    "anthropic>=0.18.0",
    "ollama>=0.1.0",
]

# Development
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
threadline = "threadline.cli.main:app"
```

---

## Database Schema (SQLite)

```sql
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Sources: original imported files
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL CHECK (file_type IN ('markdown', 'image')),
    raw_text TEXT,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_sources_hash ON sources(file_hash);

-- Entries: individual thought-units
CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    title TEXT,
    entry_date TEXT,  -- ISO format YYYY-MM-DD
    location TEXT,
    entry_type TEXT,
    entry_type_confidence REAL,
    summary_quote TEXT,
    embedding BLOB,  -- 384-dim float32 = 1536 bytes
    source_line_start INTEGER,
    source_line_end INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_entries_source ON entries(source_id);
CREATE INDEX idx_entries_date ON entries(entry_date);
CREATE INDEX idx_entries_type ON entries(entry_type);

-- Tags: user-defined labels
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Entry-Tag junction
CREATE TABLE entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX idx_entry_tags_tag ON entry_tags(tag_id);

-- Themes: auto-extracted topics
CREATE TABLE themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,  -- BERTopic's topic number (-1 = outliers)
    name TEXT NOT NULL,
    keywords TEXT,  -- JSON: [{"word": "faith", "weight": 0.12}, ...]
    representative_docs TEXT,  -- JSON: [entry_id, ...]
    entry_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Entry-Theme junction
CREATE TABLE entry_themes (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    probability REAL,
    PRIMARY KEY (entry_id, theme_id)
);

CREATE INDEX idx_entry_themes_theme ON entry_themes(theme_id);

-- Model runs: track processing history
CREATE TABLE model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL CHECK (run_type IN ('embedding', 'classification', 'themes')),
    model_name TEXT NOT NULL,
    model_version TEXT,
    entries_processed INTEGER,
    run_at TEXT DEFAULT (datetime('now'))
);

-- sqlite-vss virtual table for similarity search
-- Created programmatically after loading extension:
-- CREATE VIRTUAL TABLE entries_vss USING vss0(embedding(384));
```

---

## Key Design Decisions

### 1. Repository Pattern for Database

**Why:** Isolates SQL from business logic. Makes testing easier (mock repos). Clear API for data access.

```python
# Instead of SQL scattered everywhere:
entries = repo.list(entry_types=["thought"], tag_ids=[1, 2], limit=50)

# Not:
cursor.execute("SELECT * FROM entries WHERE entry_type IN (?, ?) ...", ...)
```

### 2. Pydantic Models Throughout

**Why:** Type safety, validation, serialization. Clear contracts between layers.

```python
class EntryCreate(BaseModel):
    source_id: int
    content: str
    title: str | None = None
    entry_type: str | None = None
    embedding: bytes | None = None

class Entry(EntryCreate):
    id: int
    created_at: datetime
    tags: list[Tag] = []
```

### 3. Lazy Model Loading

**Why:** Don't load 2GB of models until needed. First use triggers download.

```python
class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None  # Lazy

    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model
```

### 4. Textual for TUI

**Why:** Modern, async, CSS-like styling, good documentation. Handles infinite scroll well with `ListView`.

### 5. sqlite-vss for Vector Search

**Why:** No external service. Single file. Fast enough for <100k entries. Integrates with existing SQLite queries.

---

## Testing Strategy

```
tests/
├── conftest.py              # Fixtures: temp db, sample entries, mock models
├── test_core/
│   ├── test_chunker.py      # Unit: paragraph splitting edge cases
│   ├── test_classifier.py   # Unit: mock model, verify label mapping
│   ├── test_embedder.py     # Integration: actual model, verify dimensions
│   └── test_similarity.py   # Unit: cosine similarity math
├── test_db/
│   ├── test_schema.py       # Integration: migrations, constraints
│   └── test_repositories.py # Integration: CRUD operations
├── test_ingest/
│   ├── test_pipeline.py     # Integration: full ingest flow
│   ├── test_markdown.py     # Unit: frontmatter parsing
│   └── test_ocr.py          # Integration: mock/real OCR
└── test_tui/
    └── test_app.py          # Textual's pilot for UI testing
```

**Key fixtures:**

```python
# conftest.py
@pytest.fixture
def temp_db(tmp_path):
    """Fresh SQLite database for each test."""
    db_path = tmp_path / "test.db"
    conn = init_database(db_path)
    yield conn
    conn.close()

@pytest.fixture
def sample_entries(temp_db):
    """Pre-populated entries for testing."""
    repo = EntryRepository(temp_db)
    entries = [
        EntryCreate(source_id=1, content="This is a thought about life."),
        EntryCreate(source_id=1, content="- [ ] Buy groceries\n- [ ] Call mom"),
    ]
    return [repo.create(e) for e in entries]

@pytest.fixture
def mock_embedder():
    """Fast mock that returns random vectors."""
    class MockEmbedder:
        def embed(self, text): return np.random.rand(384).astype(np.float32)
    return MockEmbedder()
```

---

## Future Considerations

### Performance Scaling

If entry count exceeds 100k:
- Consider DuckDB for analytics queries
- Move embeddings to separate file (memory-mapped)
- Add full-text search index (FTS5)

### Plugin System

Potential extension points:
- Custom chunking strategies
- Additional classification labels
- Export formats
- Theme naming via LLM

### Sync/Backup

Future options:
- SQLite backup to cloud (S3, iCloud)
- Git-based sync for originals/
- Export to Obsidian/Notion format
