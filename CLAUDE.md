# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A PDF semantic search pipeline (Phase 1 of a larger project that will grow into RAG, then Knowledge Graphs). Upload a PDF, it gets chunked and embedded, and you can then run natural-language queries against it and get back the exact matching text with page/char location, highlighted in context.

Tech stack:
- **Object storage**: MinIO (Docker) — stores the original PDF bytes, keyed by a generated `pdf_id` UUID
- **Queue**: RabbitMQ (Docker) — decouples upload (fast, user-facing) from processing (slow, background)
- **Task status**: SQLite (`tasks.db`, WAL mode) — tracks `UPLOADED` → `PROCESSING` → `INDEXED`/`FAILED` per pdf_id
- **Embedding model**: `all-MiniLM-L6-v2` (sentence-transformers) — symmetric retrieval, 384-dim, same model embeds both documents and queries
- **Vector DB**: Cloudflare Vectorize (cloud) — stores embeddings + metadata, queried via both the `cloudflare` SDK and raw REST calls
- **API**: FastAPI, serving a static HTML/JS frontend from `src/static/`

## This is a learning project — read this before touching code

This is **not** a production system. It's a personal learning project (an internship exercise) whose entire point is for the user to understand, line by line, how a semantic search pipeline works. Optimizing the code or making it "more correct" by some professional standard is not the goal — the user's understanding of every line is the goal. This overrides the general instinct to refactor, abstract, or modernize code.

Follow these rules on every task in this repo:

- **Never restructure at a high level without being asked.** Do not introduce new abstractions, design patterns, folder/package structures, dependency-injection layers, config frameworks, or "proper" software-architecture patterns (e.g. repositories, service layers, ORMs) unless the user explicitly asks for that specific change. The current flat, bare-import, single-file-per-concern structure in `src/` is intentional and should stay recognizable to the user.
- **Keep changes small and local.** Prefer the smallest diff that fixes the actual problem over a rewrite, even if a rewrite would be "cleaner." If a bug fix could be done as a one-line change or a broader refactor, do the one-line change.
- **Explain, don't just do.** Before or alongside any code change, explain *what* was wrong/needed and *why* the fix works, in plain terms — assume the user wants to be able to reproduce the reasoning themselves next time, not just get working code.
- **Prefer simple, explicit code over clever or idiomatic-but-opaque code.** Basic loops over dense comprehensions, explicit steps over magic one-liners, standard-library approaches over adding a new dependency — even if a library or pattern is more "correct," if it adds a concept the user hasn't used yet, flag that tradeoff instead of silently adding it.
- **When adding something genuinely new (a library, pattern, or concept), teach it.** Briefly explain what it is and why it's the right tool here, as if the user hasn't seen it before — don't assume prior familiarity.
- **Ask before scope creep.** If a request could reasonably be satisfied with a small fix or with a bigger improvement, default to asking which the user wants rather than assuming the bigger one.

## Running it locally

```
# 1. Start MinIO + RabbitMQ (requires Docker Desktop; on Windows this needs WSL2)
docker compose up -d

# 2. Install dependencies (editable install from pyproject.toml)
pip install -e .

# 3. One-time only: create the Cloudflare Vectorize index + metadata indexes
python src/vectorize_setup.py

# 4. Run BOTH of these in separate terminals — the app is split across two processes
python src/main.py      # FastAPI app: upload endpoint, search endpoint, serves frontend at http://127.0.0.1:8000
python src/worker.py    # RabbitMQ consumer: does the actual chunk/embed/insert work
```

MinIO console: `http://127.0.0.1:9001` (default creds `admin` / `admin123`, set in `docker-compose.yml`). RabbitMQ management UI: `http://127.0.0.1:15672`.

Config is loaded from a `.env` file at the project root (see `src/config.py` for the full variable list: `MINIO_*`, `CLOUDFLARE_*`, `VECTORIZE_INDEX_NAME`). There is no `.env.example` currently — check `src/config.py` for the required keys.

## Architecture

### Two-process split: `main.py` (API) vs `worker.py` (processing)

`main.py`'s `/upload` endpoint does three things synchronously and returns immediately: saves the PDF to MinIO, creates a `tasks` row with status `UPLOADED`, and publishes `{pdf_id}` onto the `pdf_tasks` RabbitMQ queue. It does **not** chunk, embed, or touch Vectorize.

`worker.py` consumes `pdf_tasks` one message at a time (`prefetch_count=1`), looks up the task in SQLite, and calls `ingest.process_pdf()`, which re-downloads the PDF from MinIO and runs it through chunking → embedding → Vectorize insert. Status transitions: `UPLOADED` → `PROCESSING` → `INDEXED` on success, or back to `UPLOADED` (requeued, up to `MAX_RETRIES=3`) / `FAILED` (sent to `pdf_tasks_dlq`) on error. **This means the worker can crash and resume mid-pipeline** — it re-derives everything from the pdf_id rather than holding state in memory, so always keep `process_pdf` idempotent when modifying it.

### The "pointer index, real content elsewhere" pattern

Vectorize does **not** store chunk text — only the embedding vector + metadata (`pdf_id`, `page_number`, `chunk_index`, `char_start`, `char_end`, `word_count`, `source_filename`). To return actual text for a search hit, `main.py`'s `/search` endpoint takes each Vectorize match's metadata and calls `retrieval.get_highlighted_chunk()`, which re-fetches the PDF from MinIO and re-derives the page text on the fly, then slices it with the stored `char_start`/`char_end`.

This makes exact page-text reconstruction load-bearing: `extraction.build_page_text_from_blocks()` is the **single source of truth** for joining PyMuPDF blocks into page text (blocks joined with `"\n\n"`). `chunking.py` computes char offsets against this same reconstruction when building chunks, and `retrieval.py` calls the identical function when re-deriving page text at query time. **If you change how blocks are joined in one place, you must change it in both, or every stored char offset in Vectorize becomes silently wrong** (Vectorize has no text to invalidate against — offsets would just quietly point at the wrong text).

Vector IDs are deterministic: `{pdf_id}_p{page_number}_c{chunk_index}`. `vectorize_delete.py` exploits this — it re-chunks the PDF (cheap, no embedding needed) purely to regenerate the same IDs for deletion, rather than tracking them separately.

### Pipeline stages (`src/`)

1. `extraction.py` — PyMuPDF (`fitz`) pulls text blocks per page with bounding boxes
2. `chunking.py` — groups blocks into ~100-word chunks (`MAX_CHUNK_WORDS`), falling back to sentence-level splitting for oversized blocks, with ~10% word overlap carried into the next chunk (`OVERLAP_WORDS`). Tracks exact `core_char_start`/`core_char_end` offsets into the reconstructed page text
3. `embeddings.py` — `all-MiniLM-L6-v2`, loaded once at module import (`_model` global) — expensive to reload, don't re-instantiate `SentenceTransformer` per call
4. `vectorize_insert.py` / `vectorize_query.py` / `vectorize_delete.py` — talk to Cloudflare Vectorize. Insert and query use the raw REST API directly (`requests`); delete and setup use the `cloudflare` SDK client from `vectorize_setup.py`. Both `ACCOUNT_ID`/`API_TOKEN`/`INDEX_NAME` are imported from `vectorize_setup.py`, not re-read from config, so that module is a de facto shared client singleton
5. `storage.py` — MinIO upload/download/delete/list, keyed by `{pdf_id}.pdf`; original filename is preserved as MinIO object metadata since the object key itself is a UUID
6. `database.py` — SQLite task-status tracking; `init_db()` runs at import time, so importing this module always ensures the table exists

Each pipeline module (`extraction.py`, `chunking.py`, `embeddings.py`, `vectorize_*.py`, `retrieval.py`) has a `if __name__ == "__main__"` block for standalone manual testing — e.g. `python src/extraction.py` prompts for a PDF path and prints the first few blocks. Useful for isolating a stage when debugging without running the full upload → queue → worker flow.

### Module resolution

Modules within `src/` import each other with bare names (`from storage import ...`, not `from src.storage import ...`) — there's no package-relative structure, so `src/` itself needs to be on `sys.path` (it works because you run scripts from inside `src/`, or via the editable install). Keep new modules at the top level of `src/` and use the same bare-import style.
