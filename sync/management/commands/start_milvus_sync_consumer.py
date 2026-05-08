import signal
import sys
from threading import Timer
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.tc_pulsar.consumers.milvus_sync_consumer import MilvusSyncConsumer

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Start MilvusSync consumer"

    def handle(self, *args, **kwargs):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
        self.consumer = MilvusSyncConsumer()
        self.consumer.run()

    def _shutdown(self, signum, frame):
        signame = signal.Signals(signum).name
        logger.info(f"Received {signame}, shutting down gracefully...")
        self.consumer.stop()

        def force_exit():
            logger.error("Force exit - graceful shutdown timeout")
            sys.exit(1)

        Timer(30.0, force_exit).start()
