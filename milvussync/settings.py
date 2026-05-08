from decouple import config

SECRET_KEY = config("DJANGO_SECRET_KEY", default="unsafe-secret-key")
DEBUG = config("DEBUG", default=False, cast=bool)
DJANGO_ENVIRONMENT = config("DJANGO_ENVIRONMENT", default="production")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "sync.apps.SyncConfig",
]

ROOT_URLCONF = "milvussync.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

# No persistent Django state needed — in-memory SQLite satisfies Django's startup checks
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "sync": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "pulsar": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# --- Pulsar (used by tc_pulsar consumers; not used by the auto-sync path) ---
PULSAR_URL = config("PULSAR_URL", default="pulsar://localhost:6650")
PULSAR_NAMESPACE = config("PULSAR_NAMESPACE", default="default")
PULSAR_TENANT = config("PULSAR_TENANT", default="public")
PULSAR_TOPIC = config("PULSAR_TOPIC", default="tender-title-sync")

# --- Milvus ---
MILVUS_URI = config("MILVUS_URI", default="http://host.docker.internal:19530")
MILVUS_TOKEN = config("MILVUS_TOKEN", default="")

# Active collection used by auto-sync and search
TENDER_SEARCH_COLLECTION = config("TENDER_SEARCH_COLLECTION", default="tender_search")
TENDER_SEARCH_VECTOR_DIM = config("TENDER_SEARCH_VECTOR_DIM", default=1024, cast=int)

# Legacy collection used by the Pulsar-based MilvusSyncConsumer only
MILVUS_COLLECTION = config("MILVUS_COLLECTION", default="tenders")
MILVUS_VECTOR_DIM = config("MILVUS_VECTOR_DIM", default=1536, cast=int)

# --- BGE embedding model (auto-sync and search) ---
EMBEDDING_MODEL_NAME = config("EMBEDDING_MODEL_NAME", default="BAAI/bge-large-en-v1.5")
RERANKER_MODEL_NAME = config("RERANKER_MODEL_NAME", default="BAAI/bge-reranker-base")

# --- OpenAI (used by openai_provider.py / MilvusSyncConsumer; not auto-sync) ---
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_EMBEDDING_MODEL = config("OPENAI_EMBEDDING_MODEL", default="text-embedding-ada-002")

# --- PostgreSQL ---
POSTGRES_HOST = config("POSTGRES_HOST", default="localhost")
POSTGRES_PORT = config("POSTGRES_PORT", default=5432, cast=int)
POSTGRES_DB = config("POSTGRES_DB", default="tenders")
POSTGRES_USER = config("POSTGRES_USER", default="postgres")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD", default="password")
POSTGRES_SSL_MODE = config("POSTGRES_SSL_MODE", default="prefer")
POSTGRES_CONNECT_TIMEOUT = config("POSTGRES_CONNECT_TIMEOUT", default=5, cast=int)

# --- Meilisearch (keyword search) ---
MEILISEARCH_URL = config("MEILISEARCH_URL", default="http://localhost:7700")
MEILISEARCH_API_KEY = config("MEILISEARCH_API_KEY", default="")

# --- Auto-sync (PostgreSQL → BGE embeddings → Milvus + Meilisearch) ---
AUTO_SYNC_ENABLED = config("AUTO_SYNC_ENABLED", default=True, cast=bool)
AUTO_SYNC_INTERVAL_SECONDS = config("AUTO_SYNC_INTERVAL_SECONDS", default=10, cast=int)
SYNC_STATE_FILE = config("SYNC_STATE_FILE", default="sync_state.json")

# How many ANN candidates to fetch before reranking (candidate_limit = limit × factor)
ANN_CANDIDATES_FACTOR = config("ANN_CANDIDATES_FACTOR", default=3, cast=int)

# --- Pulsar consumer tuning ---
MILVUS_SYNC_UNACKED_TIMEOUT_MS = config(
    "MILVUS_SYNC_UNACKED_TIMEOUT_MS", default=5 * 60 * 1000, cast=int
)
