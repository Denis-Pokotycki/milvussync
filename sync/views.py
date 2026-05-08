import json
import os
import time

import psycopg2.extras
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

from sync.postgres.connection import get_connection
from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient

_FAVICON_SVG = """\
<svg width="32" height="32" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="30" height="30" rx="6" fill="#212529"/>
  <line x1="15" y1="15" x2="4"  y2="5"  stroke="white" stroke-width="1.4" stroke-opacity="0.5"/>
  <line x1="15" y1="15" x2="26" y2="5"  stroke="white" stroke-width="1.4" stroke-opacity="0.5"/>
  <line x1="15" y1="15" x2="4"  y2="25" stroke="white" stroke-width="1.4" stroke-opacity="0.5"/>
  <line x1="15" y1="15" x2="26" y2="25" stroke="white" stroke-width="1.4" stroke-opacity="0.5"/>
  <line x1="15" y1="15" x2="15" y2="3"  stroke="white" stroke-width="1.4" stroke-opacity="0.5"/>
  <circle cx="15" cy="15" r="3.5" fill="white"/>
  <circle cx="4"  cy="5"  r="2.8" fill="#60a5fa"/>
  <circle cx="26" cy="5"  r="2.8" fill="#34d399"/>
  <circle cx="4"  cy="25" r="2.8" fill="#f472b6"/>
  <circle cx="26" cy="25" r="2.8" fill="#a78bfa"/>
  <circle cx="15" cy="3"  r="2.8" fill="#fbbf24"/>
</svg>"""


def favicon(request):
    return HttpResponse(_FAVICON_SVG, content_type="image/svg+xml")


# Singletons — loaded once per worker process, never reset between requests
_embedder = None
_reranker = None
_milvus_client = None
_meili_client = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sync.embeddings.bge_provider import BGEEmbeddingProvider
        _embedder = BGEEmbeddingProvider(settings.EMBEDDING_MODEL_NAME)
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sync.embeddings.reranker_provider import BGERerankerProvider
        _reranker = BGERerankerProvider(settings.RERANKER_MODEL_NAME)
    return _reranker


def _get_milvus_client() -> TenderSearchMilvusClient:
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = TenderSearchMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.TENDER_SEARCH_COLLECTION,
            vector_dim=settings.TENDER_SEARCH_VECTOR_DIM,
        )
    return _milvus_client


def _get_meili_client():
    global _meili_client
    if _meili_client is None:
        from sync.tc_meilisearch.client import TenderSearchMeilisearchClient
        _meili_client = TenderSearchMeilisearchClient(
            url=settings.MEILISEARCH_URL,
            api_key=settings.MEILISEARCH_API_KEY,
        )
    return _meili_client


def rrf_fusion(
    keyword_results: list[dict],
    semantic_results: list[dict],
    k: int = 60,
    limit: int = 10,
) -> list[dict]:
    """Reciprocal Rank Fusion over two ranked lists. score = Σ 1/(k + rank_i)."""
    rrf_scores: dict[str, float] = {}
    registry: dict[str, dict] = {}

    for rank, r in enumerate(keyword_results, start=1):
        pk = r["pk"]
        rrf_scores[pk] = rrf_scores.get(pk, 0.0) + 1.0 / (k + rank)
        registry[pk] = r

    for rank, r in enumerate(semantic_results, start=1):
        pk = r["pk"]
        rrf_scores[pk] = rrf_scores.get(pk, 0.0) + 1.0 / (k + rank)
        registry.setdefault(pk, r)

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{**registry[pk], "rrf_score": round(score, 6)} for pk, score in ranked]


def dashboard(request):
    client = _get_milvus_client()
    healthy = client.healthcheck()
    records = client.list_records(limit=100) if healthy else []
    count = client.count() if healthy else 0

    return render(request, "sync/dashboard.html", {
        "healthy": healthy,
        "records": records,
        "count": count,
        "collection": settings.TENDER_SEARCH_COLLECTION,
        "milvus_uri": settings.MILVUS_URI,
        "active_page": "milvus",
    })


def postgres_view(request):
    q_title = request.GET.get("q", "").strip()
    q_lang  = request.GET.get("lang", "").strip()
    q_nut   = request.GET.get("nut", "").strip()
    q_cpv   = request.GET.get("cpv", "").strip()

    rows = []
    languages = []
    nut_regions = []
    total = 0
    unique_tenders = 0
    error = None

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                conditions = []
                params = {}
                if q_title:
                    conditions.append("title ILIKE %(title)s")
                    params["title"] = f"%{q_title}%"
                if q_lang:
                    conditions.append("language_code = %(lang)s")
                    params["lang"] = q_lang
                if q_nut:
                    conditions.append("(nut_code ILIKE %(nut)s OR nut_label ILIKE %(nut)s)")
                    params["nut"] = f"%{q_nut}%"
                if q_cpv:
                    conditions.append("%(cpv)s = ANY(cpv_codes)")
                    params["cpv"] = q_cpv

                where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

                cur.execute(f"""
                    SELECT
                        pk, tender_id, platform_id, tender_national_id,
                        publication_date::text  AS publication_date,
                        closing_date::text      AS closing_date,
                        COALESCE(estimated_total_value, 0) AS estimated_total_value,
                        language_code, title,
                        COALESCE(nut_code, '')  AS nut_code,
                        COALESCE(nut_label, '') AS nut_label,
                        COALESCE(cpv_codes, ARRAY[]::text[]) AS cpv_codes,
                        created_at, updated_at
                    FROM tender_translations_demo
                    {where}
                    ORDER BY tender_id, language_code
                """, params)
                rows = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT
                        COUNT(*)                          AS total,
                        COUNT(DISTINCT tender_id)         AS unique_tenders,
                        ARRAY_AGG(DISTINCT language_code ORDER BY language_code) AS langs,
                        ARRAY_AGG(DISTINCT nut_code       ORDER BY nut_code)     AS nuts
                    FROM tender_translations_demo
                """)
                stats = dict(cur.fetchone())
                total          = stats["total"]
                unique_tenders = stats["unique_tenders"]
                languages      = [l for l in (stats["langs"] or []) if l]
                nut_regions    = [n for n in (stats["nuts"] or []) if n]

    except Exception as exc:
        error = str(exc)

    return render(request, "sync/postgres.html", {
        "rows": rows,
        "total": total,
        "unique_tenders": unique_tenders,
        "languages": languages,
        "nut_regions": nut_regions,
        "filtered_count": len(rows),
        "q_title": q_title,
        "q_lang": q_lang,
        "q_nut": q_nut,
        "q_cpv": q_cpv,
        "error": error,
        "db_name": settings.POSTGRES_DB,
        "active_page": "postgres",
    })


def search_view(request):
    query = request.GET.get("q", "").strip()
    limit = min(int(request.GET.get("limit", 10)), 20)

    # Fetch more ANN candidates than needed so the reranker has a richer pool to score
    ann_factor = getattr(settings, "ANN_CANDIDATES_FACTOR", 3)
    candidate_limit = limit * ann_factor

    meili_results    = []
    semantic_results = []
    hybrid_results   = []
    model_ready      = False
    reranker_ready   = False
    error            = None
    elapsed          = {}

    if query:
        try:
            t0 = time.monotonic()
            meili_results = _get_meili_client().search(query, limit=limit)
            elapsed["meili"] = (time.monotonic() - t0) * 1000

            client = _get_milvus_client()
            t0 = time.monotonic()
            embedder = _get_embedder()
            model_ready = True
            query_vec = embedder.embed_query(query)
            ann_candidates = client.search(query_embedding=query_vec, limit=candidate_limit)
            elapsed["ann"] = (time.monotonic() - t0) * 1000

            t0 = time.monotonic()
            reranker = _get_reranker()
            reranker_ready = True
            semantic_results = reranker.rerank(
                query=query,
                records=ann_candidates,
                text_field="title",
                limit=limit,
            )
            elapsed["rerank"] = (time.monotonic() - t0) * 1000

            t0 = time.monotonic()
            hybrid_results = rrf_fusion(meili_results, semantic_results, limit=limit)
            elapsed["rrf"] = (time.monotonic() - t0) * 1000
            elapsed["total"] = elapsed["meili"] + elapsed["ann"] + elapsed["rerank"] + elapsed["rrf"]

        except Exception as exc:
            error = str(exc)

    return render(request, "sync/search.html", {
        "query":            query,
        "limit":            limit,
        "meili_results":    meili_results,
        "semantic_results": semantic_results,
        "hybrid_results":   hybrid_results,
        "elapsed":          elapsed,
        "model_ready":      model_ready,
        "reranker_ready":   reranker_ready,
        "candidate_limit":  candidate_limit,
        "error":            error,
        "active_page":      "search",
    })


def pipeline_view(request):
    pg_total        = 0
    pg_last_updated = None
    pg_by_lang      = []
    pg_error        = None
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT COUNT(*) AS total,
                           MAX(updated_at)::text AS last_updated
                    FROM tender_translations_demo
                """)
                row = dict(cur.fetchone())
                pg_total        = row["total"]
                pg_last_updated = row["last_updated"]

                cur.execute("""
                    SELECT language_code, COUNT(*) AS cnt
                    FROM tender_translations_demo
                    GROUP BY language_code
                    ORDER BY cnt DESC
                """)
                pg_by_lang = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        pg_error = str(exc)

    cursor_ts    = None
    cursor_error = None
    state_file   = settings.SYNC_STATE_FILE
    try:
        state_path = state_file if os.path.isabs(state_file) else \
                     os.path.join(os.path.dirname(os.path.dirname(__file__)), state_file)
        with open(state_path) as f:
            cursor_ts = json.load(f).get("last_synced_at")
    except FileNotFoundError:
        cursor_error = "sync_state.json not found — auto-sync has not run yet"
    except Exception as exc:
        cursor_error = str(exc)

    milvus_count   = 0
    milvus_healthy = False
    milvus_error   = None
    try:
        client = _get_milvus_client()
        milvus_healthy = client.healthcheck()
        if milvus_healthy:
            milvus_count = client.count()
    except Exception as exc:
        milvus_error = str(exc)

    pending    = max(0, pg_total - milvus_count)
    synced_pct = round(milvus_count / pg_total * 100) if pg_total else 0

    from sync.autosync import is_running as autosync_is_running
    autosync_running  = autosync_is_running()
    autosync_interval = getattr(settings, "AUTO_SYNC_INTERVAL_SECONDS", 10)

    return render(request, "sync/pipeline.html", {
        "pg_total":          pg_total,
        "pg_last_updated":   pg_last_updated,
        "pg_by_lang":        pg_by_lang,
        "pg_error":          pg_error,
        "cursor_ts":         cursor_ts,
        "cursor_error":      cursor_error,
        "milvus_count":      milvus_count,
        "milvus_healthy":    milvus_healthy,
        "milvus_error":      milvus_error,
        "pending":           pending,
        "synced_pct":        synced_pct,
        "pulsar_topic":      settings.PULSAR_TOPIC,
        "collection":        settings.TENDER_SEARCH_COLLECTION,
        "autosync_running":  autosync_running,
        "autosync_interval": autosync_interval,
        "active_page":       "pipeline",
    })
