"""
Start the TenderSearchConsumer to process tender-title-sync messages.

Usage:
  python manage.py run_consumer
  python manage.py run_consumer --subscription my_custom_sub
  python manage.py run_consumer --earliest          # read from beginning of topic (new sub only)
  python manage.py run_consumer --earliest --subscription demo_sub
"""
import signal
import pulsar
from django.conf import settings
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.tc_pulsar.consumers.tender_search_consumer import TenderSearchConsumer

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Run the TenderSearchConsumer (reads Pulsar, embeds titles, upserts to Milvus)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--subscription",
            type=str,
            default=None,
            help="Override the Pulsar subscription name.",
        )
        parser.add_argument(
            "--earliest",
            action="store_true",
            help=(
                "Start subscription from the earliest available message in the topic. "
                "Only effective for a brand-new subscription name. "
                "Use this when seeding Milvus from an existing Pulsar topic."
            ),
        )

    def handle(self, *args, **options):
        subscription = options["subscription"] or (
            f"{settings.DJANGO_ENVIRONMENT}_TenderSearchConsumer"
        )

        consumer_options = {}
        if options["earliest"]:
            consumer_options["initial_position"] = pulsar.InitialPosition.Earliest
            logger.info("run_consumer.initial_position", position="Earliest")

        consumer = TenderSearchConsumer(
            subscription_name=subscription,
            consumer_options=consumer_options or None,
        )

        def _stop(signum, frame):
            logger.info("run_consumer.signal_received", signum=signum)
            consumer.stop()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        logger.info("run_consumer.starting", subscription=subscription)
        consumer.run()
        logger.info("run_consumer.stopped")
