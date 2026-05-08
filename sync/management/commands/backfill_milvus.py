import signal
import sys
from threading import Timer
import pulsar
from django.conf import settings
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.tc_pulsar.consumers.milvus_sync_consumer import MilvusSyncConsumer

logger = get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill Milvus by replaying all messages from the attachments topic "
        "using a dedicated backfill subscription starting at Earliest."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--subscription",
            type=str,
            default=f"{settings.DJANGO_ENVIRONMENT}_MilvusSyncConsumer_backfill",
            help="Pulsar subscription name for the backfill run.",
        )
        parser.add_argument(
            "--topic",
            type=str,
            default="attachments",
            help="Pulsar topic to replay (default: attachments).",
        )

    def handle(self, *args, **options):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.consumer = MilvusSyncConsumer(
            consume_topic=options["topic"],
            subscription_name=options["subscription"],
            consumer_options={
                "initial_position": pulsar.InitialPosition.Earliest,
            },
        )
        logger.info(
            "backfill.starting",
            subscription=options["subscription"],
            topic=options["topic"],
        )
        self.consumer.run()
        logger.info("backfill.complete")

    def _shutdown(self, signum, frame):
        signame = signal.Signals(signum).name
        logger.info(f"Received {signame}, stopping backfill...")
        self.consumer.stop()

        def force_exit():
            logger.error("Force exit - graceful backfill shutdown timeout")
            sys.exit(1)

        Timer(30.0, force_exit).start()
