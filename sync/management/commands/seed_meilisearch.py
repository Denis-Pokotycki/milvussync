"""
Index all records from PostgreSQL into Meilisearch.
Run this once after adding MEILISEARCH_URL to your environment.

Usage:
  python manage.py seed_meilisearch
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from milvussync.logging import get_logger
from sync.postgres.connection import get_connection
from sync.tc_meilisearch.client import TenderSearchMeilisearchClient

logger = get_logger(__name__)

_FETCH_SQL = """
    SELECT
        pk, tender_id, platform_id, tender_national_id,
        publication_date::text  AS publication_date,
        closing_date::text      AS closing_date,
        COALESCE(estimated_total_value, 0) AS estimated_total_value,
        language_code, title,
        COALESCE(nut_code, '')  AS nut_code,
        COALESCE(nut_label, '') AS nut_label,
        COALESCE(cpv_codes, ARRAY[]::text[]) AS cpv_codes
    FROM tender_translations_demo
    ORDER BY tender_id, language_code
"""


class Command(BaseCommand):
    help = "Index all PostgreSQL tender records into Meilisearch."

    def handle(self, *args, **options):
        meili = TenderSearchMeilisearchClient(
            url=settings.MEILISEARCH_URL,
            api_key=settings.MEILISEARCH_API_KEY,
        )

        self.stdout.write("Ensuring Meilisearch index…")
        meili.ensure_index()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_FETCH_SQL)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        if not rows:
            self.stdout.write(self.style.WARNING("No records found in PostgreSQL."))
            return

        docs = [
            {
                "pk":                    r["pk"],
                "tender_id":             str(r.get("tender_id") or ""),
                "platform_id":           str(r.get("platform_id") or ""),
                "tender_national_id":    str(r.get("tender_national_id") or ""),
                "publication_date":      str(r.get("publication_date") or ""),
                "closing_date":          str(r.get("closing_date") or ""),
                "estimated_total_value": float(r.get("estimated_total_value") or 0.0),
                "language_code":         str(r.get("language_code") or ""),
                "title":                 str(r.get("title") or ""),
                "nut_code":              str(r.get("nut_code") or ""),
                "nut_label":             str(r.get("nut_label") or ""),
                "cpv_codes":             list(r.get("cpv_codes") or []),
            }
            for r in rows
        ]

        BATCH = 200
        for i in range(0, len(docs), BATCH):
            batch = docs[i : i + BATCH]
            meili.upsert_documents(batch)
            self.stdout.write(f"  Queued {i + len(batch)}/{len(docs)} documents…")

        self.stdout.write(self.style.SUCCESS(
            f"Done — {len(docs)} documents queued for indexing in Meilisearch.\n"
            f"Meilisearch indexes asynchronously; allow a few seconds for completion."
        ))
