# MilvusSync

A Django service that syncs EU public tender data from PostgreSQL into a hybrid search pipeline and serves a browser UI for comparing three retrieval strategies side by side.

---

## What it does

```text
PostgreSQL (tender_translations)
        |
        |  auto-sync background thread (every 10 s)
        v
BGE-large-en-v1.5  (1024-dim embeddings, local, free)
        |
        +----------------------+
        v                      v
Milvus (HNSW/COSINE)    Meilisearch (full-text)
  ANN semantic search     keyword search
        |                      |
        +----------+-----------+
                   v
        BGE Reranker (cross-encoder)
                   |
                   v
        RRF Fusion  (Reciprocal Rank Fusion)
                   |
                   v
        Django UI  -- 4-page browser interface
```

### Search pipeline (per query)

| Stage | Model / Engine | Output |
| --- | --- | --- |
| Keyword | Meilisearch full-text | ranked hits + score |
| Semantic ANN | BGE-large-en-v1.5 -> Milvus HNSW | top-N candidates |
| Rerank | BGE-reranker-base cross-encoder | reranked semantic results |
| Hybrid | RRF fusion -- combines keyword + semantic ranks | merged ranked list |

All four stages run on every query. The UI shows timing for each stage (ms).

#### RRF formula

```text
score(doc) = 1/(k + rank_keyword) + 1/(k + rank_semantic)
```

`rank` is each document's position in the keyword list and the semantic list (1-based). The two per-list scores are summed to get the final hybrid score.

`k = 60` is the **rank-fusion constant** from the original RRF paper (Cormack, Clarke & Buettcher, 2009). It controls how aggressively the top rank beats rank 2, 3, ...:

| k | score at rank 1 | score at rank 2 | ratio |
| --- | --- | --- | --- |
| 1 | 0.500 | 0.333 | 1.50x |
| **60** | **0.016** | **0.016** | **1.02x** |
| 200 | 0.005 | 0.005 | 1.00x |

A small `k` (e.g. 1) gives the first-ranked document a huge advantage. `k = 60` keeps the ranking sensitive to position while preventing a single top result from dominating the merged list. The value 60 is empirically validated across TREC retrieval benchmarks and is the widely-accepted default.

---

## Browser UI

Four pages served at `http://localhost:8000`:

| URL | Page | Description |
| --- | --- | --- |
| `/` | Milvus Dashboard | Collection stats, latest records |
| `/postgres/` | PostgreSQL Browser | Filterable table of all tender translations |
| `/search/` | Search Comparison | Three-column view: Keyword / Semantic / Hybrid |
| `/pipeline/` | Pipeline Monitor | Sync cursor, row counts, auto-sync status |

### Search comparison UI

![Three columns: Meilisearch Keyword, Semantic (BGE + Reranker), Hybrid RRF]

Each result card shows: rank, score, language badge, title, region (NUTS), value, CPV codes, dates.

---

## Architecture

### Auto-sync daemon

Started automatically on Django `ready()`. Runs in a background thread:

1. Polls PostgreSQL for rows with `updated_at > last_synced_at`
2. Generates BGE embeddings for each title
3. Upserts into Milvus (vector store) and Meilisearch (keyword index)
4. Saves cursor to `sync_state.json`

Any new row inserted into PostgreSQL appears in search within ~10 seconds.

### Embedding models (local, no API cost)

| Model | Use | Dimensions |
| --- | --- | --- |
| `BAAI/bge-large-en-v1.5` | Title embeddings + query encoding | 1024 |
| `BAAI/bge-reranker-base` | Cross-encoder reranking | -- |

Both models are downloaded automatically on first run via `sentence-transformers` (~1.5 GB total).

### Data model

One record per `(tender_id, language_code)` pair. Supports multilingual tenders -- the same tender can have EN, DE, FR, IT translations stored as separate searchable records.

| Field | Type | Notes |
| --- | --- | --- |
| `pk` | VARCHAR | `{tender_id}_{language_code}` -- primary key |
| `title` | VARCHAR(65535) | Source text for embedding |
| `title_embedding` | FLOAT_VECTOR(1024) | HNSW COSINE index |
| `language_code` | VARCHAR | `en`, `de`, `fr`, `it`, `es`, `pl`, `nl` ... |
| `nut_code` / `nut_label` | VARCHAR | EU NUTS region |
| `cpv_codes` | ARRAY | CPV procurement classification |
| `estimated_total_value` | FLOAT | Contract value (EUR) |
| `publication_date` / `closing_date` | VARCHAR | ISO-8601 |

---

## Quick Start

### Prerequisites

- Python 3.12+
- [Milvus](https://milvus.io/docs/install_standalone-docker.md) running (default `http://localhost:19530`)
- [Meilisearch](https://www.meilisearch.com/docs/learn/getting_started/installation) running (default `http://localhost:7700`)
- PostgreSQL running with `tender_translations_demo` table

### Install

```bash
pip install poetry
poetry install
```

### Configure

```bash
cp .env.example .env
# Edit .env -- set POSTGRES_*, MILVUS_URI, MEILISEARCH_URL
```

### Seed demo data

```bash
# Create PostgreSQL table + insert 62 demo tenders (T021-T054, 17 EU languages)
python manage.py setup_demo
python manage.py insert_demo_tenders

# Index all PostgreSQL rows into Meilisearch (one-shot full reindex)
python manage.py seed_meilisearch
```

### Run

```bash
python manage.py runserver
# -> http://localhost:8000
```

The auto-sync daemon starts automatically and begins embedding + indexing.

---

## Management Commands

| Command | Description |
| --- | --- |
| `insert_demo_tenders` | Insert 62 demo tenders (T021-T054) across 17 EU languages. `--batch 1\|2\|3\|4\|all` |
| `seed_meilisearch` | Full reindex from PostgreSQL to Meilisearch |
| `backfill_milvus` | Replay Pulsar topic from earliest offset (event-driven path) |
| `start_milvus_sync_consumer` | Start Pulsar consumer for event-driven ingestion |

---

## Tests

```bash
pytest                                      # 117 tests
pytest -v                                   # verbose
pytest --cov=sync --cov-report=term-missing # with coverage
```

117/117 passing. Core coverage:

| Module | Coverage |
| --- | --- |
| `embeddings/bge_provider.py` | 100% |
| `embeddings/reranker_provider.py` | 100% |
| `embeddings/openai_provider.py` | 100% |
| `tc_milvus/tender_search_client.py` | 100% |
| `tc_meilisearch/client.py` | 100% |
| `tc_pulsar/consumers/milvus_sync_consumer.py` | 100% |
| `management/commands/backfill_milvus.py` | 100% |
| `autosync.py` | 88% |
| `postgres/connection.py` | 100% |
| `tc_pulsar/consumers/base_consumer.py` | 72% |

---

## Project Structure

```text
MilvusSync/
+-- milvussync/                  # Django project
|   +-- settings.py              # All config via python-decouple + .env
|   +-- logging.py               # structlog JSON logging
|
+-- sync/                        # Django app
|   +-- autosync.py              # Background daemon thread
|   +-- views.py                 # Search logic, RRF fusion, all page views
|   |
|   +-- embeddings/
|   |   +-- bge_provider.py      # BGE-large embedding provider
|   |   +-- reranker_provider.py # BGE cross-encoder reranker
|   |   +-- openai_provider.py   # OpenAI ada-002 (Pulsar consumer path)
|   |
|   +-- postgres/
|   |   +-- connection.py        # psycopg2 context manager
|   |   +-- tender_repository.py # Incremental fetch with updated_at cursor
|   |
|   +-- tc_milvus/
|   |   +-- tender_search_client.py  # HNSW collection, upsert, ANN search
|   |
|   +-- tc_meilisearch/
|   |   +-- client.py            # Index management, upsert, keyword search
|   |
|   +-- tc_pulsar/consumers/     # Event-driven ingestion path (Pulsar)
|   |
|   +-- templates/sync/
|   |   +-- search.html          # Three-column hybrid search UI
|   |   +-- dashboard.html       # Milvus collection browser
|   |   +-- postgres.html        # Filterable PostgreSQL table
|   |   +-- pipeline.html        # Sync status dashboard
|   |   +-- _lang_badge.html     # Language badge partial (17 EU languages)
|   |
|   +-- management/commands/
|       +-- insert_demo_tenders.py
|       +-- seed_meilisearch.py
|       +-- backfill_milvus.py
|
+-- tests/
    +-- fakes/                   # In-memory Milvus + Pulsar fakes
    +-- conftest.py
    +-- test_consumer.py
    +-- test_embedding_provider.py
    +-- test_milvus_client.py
    +-- test_payload_mapping.py
    +-- test_backfill_command.py
    +-- test_bge_provider.py
    +-- test_reranker_provider.py
    +-- test_tender_search_client.py
    +-- test_meilisearch_client.py
    +-- test_autosync.py
    +-- test_rrf_fusion.py
```

---

## Stack

| Layer | Technology |
| --- | --- |
| Web framework | Django 5.1 |
| Vector store | Milvus 2.4 (HNSW, COSINE) |
| Keyword search | Meilisearch 0.31 |
| Embeddings | sentence-transformers (BGE-large-en-v1.5) |
| Reranker | sentence-transformers (BGE-reranker-base) |
| Database | PostgreSQL (psycopg2) |
| Logging | structlog (JSON) |
| Config | python-decouple |
| Retry | tenacity |
| Frontend | Bootstrap 5 |
| Event ingestion | Apache Pulsar (optional path) |
