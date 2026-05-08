"""
CLI semantic search against the tender_search Milvus collection.

Usage:
  python manage.py search_demo "road construction"
  python manage.py search_demo "medical equipment" --lang en --limit 5
  python manage.py search_demo "software" --cpv 72000000-5
  python manage.py search_demo "waste management" --since 2024-01-01
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.embeddings.bge_provider import BGEEmbeddingProvider
from sync.tc_milvus.tender_search_client import TenderSearchMilvusClient

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Semantic search against the tender_search Milvus collection."

    def add_arguments(self, parser):
        parser.add_argument("query", type=str, help="Natural language search query.")
        parser.add_argument(
            "--limit", type=int, default=10,
            help="Maximum number of results to return (default: 10).",
        )
        parser.add_argument(
            "--lang", type=str, default=None,
            help="Filter by language code, e.g. 'en', 'it', 'fr'.",
        )
        parser.add_argument(
            "--cpv", type=str, default=None,
            help="Filter by CPV code, e.g. '45233120-6'.",
        )
        parser.add_argument(
            "--since", type=str, default=None,
            help="Filter by publication_date >= 'YYYY-MM-DD'.",
        )

    def handle(self, *args, **options):
        query = options["query"].strip()
        if not query:
            self.stderr.write("Error: query must not be empty.")
            return

        self.stdout.write(f'\nSearching for: "{query}"')
        if options["lang"]:
            self.stdout.write(f"  Language filter : {options['lang']}")
        if options["cpv"]:
            self.stdout.write(f"  CPV filter      : {options['cpv']}")
        if options["since"]:
            self.stdout.write(f"  Since           : {options['since']}")
        self.stdout.write("")

        embedder = BGEEmbeddingProvider(settings.EMBEDDING_MODEL_NAME)
        self.stdout.write("Generating query embedding…")
        query_embedding = embedder.embed_query(query)

        milvus = TenderSearchMilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN,
            collection_name=settings.TENDER_SEARCH_COLLECTION,
            vector_dim=settings.TENDER_SEARCH_VECTOR_DIM,
        )

        hits = milvus.search(
            query_embedding=query_embedding,
            limit=options["limit"],
            language_code=options["lang"],
            cpv_code=options["cpv"],
            publication_date_gte=options["since"],
        )

        if not hits:
            self.stdout.write("No results found.")
            return

        self.stdout.write(f"Found {len(hits)} result(s):\n")
        for i, hit in enumerate(hits, start=1):
            self.stdout.write(
                f"  [{i}] score={hit['score']:.4f}  pk={hit['pk']}"
            )
            self.stdout.write(f"       lang={hit['language_code']}  "
                              f"nut={hit['nut_code']} ({hit['nut_label']})")
            self.stdout.write(f"       cpv={hit['cpv_codes']}")
            self.stdout.write(f"       pub={hit['publication_date']}  "
                              f"close={hit['closing_date']}  "
                              f"value={hit['estimated_total_value']:,.0f}")
            self.stdout.write(f"       title: {hit['title'][:120]}")
            self.stdout.write("")
