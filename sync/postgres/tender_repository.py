import psycopg2.extras
from sync.postgres.connection import get_connection

TABLE = "tender_translations_demo"

_SELECT = f"""
    SELECT
        pk,
        tender_id,
        COALESCE(platform_id, '')            AS platform_id,
        COALESCE(tender_national_id, '')      AS tender_national_id,
        COALESCE(publication_date::text, '')  AS publication_date,
        COALESCE(closing_date::text, '')      AS closing_date,
        COALESCE(estimated_total_value, 0.0)  AS estimated_total_value,
        language_code,
        title,
        COALESCE(nut_code, '')                AS nut_code,
        COALESCE(nut_label, '')               AS nut_label,
        COALESCE(cpv_codes, ARRAY[]::text[])  AS cpv_codes,
        updated_at
    FROM {TABLE}
    WHERE title IS NOT NULL AND title <> ''
      AND (%(since)s::timestamptz IS NULL OR updated_at > %(since)s::timestamptz)
    ORDER BY updated_at ASC, pk ASC
    LIMIT %(limit)s OFFSET %(offset)s
"""

_COUNT = f"""
    SELECT COUNT(*) FROM {TABLE}
    WHERE title IS NOT NULL AND title <> ''
      AND (%(since)s::timestamptz IS NULL OR updated_at > %(since)s::timestamptz)
"""


class TenderTranslationRepository:
    def fetch_page(self, offset: int, limit: int, since: str | None = None) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(_SELECT, {"since": since, "limit": limit, "offset": offset})
                return [dict(row) for row in cur.fetchall()]

    def count(self, since: str | None = None) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_COUNT, {"since": since})
                return cur.fetchone()[0]
