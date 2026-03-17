# AI News Aggregator MVP

A lightweight full-stack AI news aggregator with:
- `backend/`: FastAPI BFF that fetches and normalizes RSS and HTML news sources
- `frontend/`: Vite + React + TypeScript single-page app that consumes backend JSON API

## Project Structure

```text
.
├── backend
│   ├── app
│   │   ├── api
│   │   │   └── routes.py
│   │   ├── core
│   │   │   └── config.py
│   │   ├── models
│   │   │   └── news.py
│   │   ├── services
│   │   │   ├── html_source_service.py
│   │   │   ├── news_service.py
│   │   │   └── rss_service.py
│   │   └── main.py
│   ├── tests
│   │   ├── test_news_service.py
│   │   └── test_rss_service.py
│   └── pyproject.toml
├── frontend
│   ├── src
│   │   ├── components
│   │   │   ├── NewsCard.tsx
│   │   │   └── NewsList.tsx
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── types.ts
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Backend API

- `GET /api/health` -> health status
- `GET /api/sources` -> configured feed sources
- `GET /api/news` -> reads stored articles from PostgreSQL only (sorted by `published_at` desc, nulls last)
- `POST /api/sync` -> fetches live sources, normalizes items, upserts into PostgreSQL by article URL

`GET /api/news` supports pagination:
- `limit` (default `20`)
- `offset` (default `0`)

Each news item has this schema:
- `id`
- `source_id`
- `source_name`
- `title`
- `link`
- `summary`
- `published_at` (ISO 8601 or `null`)
- `announced_at` (optional, currently for arXiv enrichment)
- `original_published_at` (optional, currently for arXiv enrichment)
- `updated_at` (optional, currently for arXiv enrichment)
- `author` (optional)
- `tags` (optional list)

Sync response (`POST /api/sync`) includes:
- `status`
- `total_fetched`
- `inserted`
- `updated`
- `failed_sources`

## Local Development

### 1) Run backend (FastAPI + uv)

Requirements:
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 14+

Create database:

```bash
createdb ai_news
```

Set `DATABASE_URL`:

```bash
pg_ctl -D /opt/homebrew/var/postgresql@18 stop -m immediate
rm /opt/homebrew/var/postgresql@18/postmaster.pid
pg_ctl -D /opt/homebrew/var/postgresql@18 -l /opt/homebrew/var/log/postgresql@18.log start
pg_isready -h localhost -p 5432
psql -h localhost -U denysord88 -d ai_news -c "SELECT 1;"
export DATABASE_URL="postgresql+psycopg://denysord88@localhost:5432/ai_news"
```

Commands:

```bash
cd backend
uv sync --active --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run on `http://localhost:8000`.
Tables are initialized automatically on backend startup via SQLAlchemy `create_all`.

### 2) Run frontend (Vite + React)

Requirements:
- Node.js 20+
- npm

Commands in a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on `http://localhost:5173`.

By default it calls `http://localhost:8000`.

Optional override:

```bash
cd frontend
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
```

## Tests

Run backend tests:

```bash
cd backend
uv run pytest
```

The backend test suite validates:
- RSS normalization behavior
- HTML source parsing behavior
- Per-source cap (`max_items`) and descending date sorting
- Aggregation behavior with partial source failures
- API route contract shape for `/api/health`, `/api/sources`, and `/api/news`

## Persistence Model

News is stored in PostgreSQL table `articles` with:
- URL as unique key (`url`)
- indexes on `published_at` and `source_id`
- upsert semantics on sync:
  - existing URL -> update fields + `updated_record_at` + `last_seen_at`
  - new URL -> insert row

`GET /api/news` reads this table only.
`POST /api/sync` is the manual refresh endpoint that fetches live sources and upserts rows.

## Frontend Sync Flow

- On page load, frontend calls `GET /api/news` and renders only stored DB articles.
- The `Load new posts` button calls `POST /api/sync`.
- After successful sync, frontend calls `GET /api/news` again to refresh the list.
- The UI uses infinite scroll pagination: first 20 items, then next 20 while scrolling.

## Feed Configuration (Add More Sources)

Edit `backend/app/core/config.py` and append new `FeedSource` items to `config.sources`.

RSS example:

```python
FeedSource(
    id="another-source",
    name="Another Source",
    type="rss",
    url="https://example.com/rss.xml",
    max_items=20,
)
```

HTML example:

```python
FeedSource(
    id="another-html-source",
    name="Another HTML Source",
    type="html",
    url="https://example.com/blog",
    max_items=20,
)
```

No core logic changes are needed when adding sources.

## Google AI Sources

The following RSS feeds are configured:
- `Google Gemini`: `https://blog.google/products-and-platforms/products/gemini/rss/`
- `Google AI`: `https://blog.google/innovation-and-ai/rss/`

## Cognition / Devin Source

- `Cognition (Devin)`: `https://cognition.ai/blog/1`

This source is ingested via HTML parsing in `html_source_service.py` because there is no official RSS feed used in this project for these updates.

## Research and Open Source Sources

The following RSS feeds are configured:
- `arXiv AI`: `https://export.arxiv.org/rss/cs.AI`
- `HuggingFace Blog`: `https://huggingface.co/blog/feed.xml`

## arXiv Date Enrichment

- arXiv papers are discovered from the RSS feed (`arxiv_ai` source).
- The backend then enriches those items via the arXiv API (`http://export.arxiv.org/api/query`) using extracted arXiv IDs.
- For arXiv items, `published_at` uses this priority:
  1. `original_published_at` (submitted date from arXiv API)
  2. `updated_at` (from arXiv API)
  3. `announced_at` (original RSS date)
  4. fallback to existing RSS `published_at`
- Additional optional fields exposed on arXiv items:
  - `announced_at`
  - `original_published_at`
  - `updated_at`

## Adding New HTML Sources

1. Add a `FeedSource` with `type="html"` in `backend/app/core/config.py`.
2. If the new site follows existing link-card patterns, `HTMLSourceService` may parse it automatically.
3. If the structure is custom, add a source-specific branch in `backend/app/services/html_source_service.py` with tailored selectors/path hints.
4. Keep output normalized to the shared `NewsItem` schema.

## Notes

- Backend fetches all sources asynchronously.
- Each source is capped by `max_items` (currently 20 per source).
- Source ingestion uses provider classes per source type:
  - `RssSourceProvider`
  - `HtmlSourceProvider`
- If one source fails, other sources are still returned.
- Frontend does not parse source pages directly; it uses backend JSON only.
- URL is used as the database uniqueness key for articles.
