import contextlib
import psycopg2
import psycopg2.extras
from django.conf import settings


@contextlib.contextmanager
def get_connection():
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        sslmode=settings.POSTGRES_SSL_MODE,
        connect_timeout=getattr(settings, "POSTGRES_CONNECT_TIMEOUT", 5),
    )
    try:
        yield conn
    finally:
        conn.close()
