"""
Pulsar producer: reads PostgreSQL tender_translations_demo and publishes
each row as a JSON message to the tender-title-sync topic.

Usage:
  python manage.py run_producer              # run once, then exit
  python manage.py run_producer --loop       # poll continuously
  python manage.py run_producer --reset      # clear sync state, full re-publish
"""
import json
import os
import signal
import time
from datetime import datetime, timezone

import pulsar
from django.conf import settings
from django.core.management.base import BaseCommand
from milvussync.logging import get_logger
from sync.postgres.tender_repository import TenderTranslationRepository

logger = get_logger(__name__)


def _load_state(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _build_topic(tenant: str, namespace: str, topic: str) -> str:
    return f"persistent://{tenant}/{namespace}/{topic}"


class Command(BaseCommand):
    help = "Read PostgreSQL tender translations and publish to Pulsar."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop", action="store_true",
            help="Poll PostgreSQL continuously instead of exiting after one pass.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Ignore stored sync cursor and publish all rows from the beginning.",
        )
        parser.add_argument(
            "--interval", type=int, default=None,
            help="Override SYNC_POLL_INTERVAL_SECONDS for this run.",
        )

    def handle(self, *args, **options):
        self._running = True
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

        state_path = settings.SYNC_STATE_FILE
        if options["reset"] and os.path.exists(state_path):
            os.remove(state_path)
            logger.info("run_producer.state_reset", path=state_path)

        poll_interval = options["interval"] or settings.SYNC_POLL_INTERVAL_SECONDS
        topic = _build_topic(
            settings.PULSAR_TENANT,
            settings.PULSAR_NAMESPACE,
            settings.PULSAR_TOPIC,
        )

        client = pulsar.Client(
            settings.PULSAR_URL,
            logger=pulsar.ConsoleLogger(pulsar.LoggerLevel.Error),
        )
        producer = client.create_producer(topic)
        repo = TenderTranslationRepository()

        try:
            while self._running:
                self._run_pass(producer, repo, state_path)
                if not options["loop"]:
                    break
                logger.info("run_producer.sleeping", seconds=poll_interval)
                for _ in range(poll_interval):
                    if not self._running:
                        break
                    time.sleep(1)
        finally:
            producer.flush()
            producer.close()
            client.close()
            logger.info("run_producer.stopped")

    def _run_pass(self, producer, repo, state_path: str):
        state = _load_state(state_path)
        since = state.get("last_synced_at")

        total = repo.count(since=since)
        if total == 0:
            logger.info("run_producer.no_new_rows", since=since)
            return

        logger.info("run_producer.pass_start", total=total, since=since)
        batch_size = settings.SYNC_BATCH_SIZE
        offset = 0
        published = 0
        latest_updated_at: str | None = None

        while offset < total and self._running:
            rows = repo.fetch_page(offset=offset, limit=batch_size, since=since)
            if not rows:
                break

            for row in rows:
                payload = {
                    "pk": row["pk"],
                    "tender_id": row["tender_id"],
                    "platform_id": row["platform_id"],
                    "tender_national_id": row["tender_national_id"],
                    "publication_date": row["publication_date"],
                    "closing_date": row["closing_date"],
                    "estimated_total_value": float(row["estimated_total_value"] or 0.0),
                    "language_code": row["language_code"],
                    "title": row["title"],
                    "nut_code": row["nut_code"],
                    "nut_label": row["nut_label"],
                    "cpv_codes": list(row["cpv_codes"] or []),
                }
                producer.send(json.dumps(payload).encode("utf-8"))
                published += 1
                row_ts = row.get("updated_at")
                if row_ts is not None:
                    # psycopg2 returns a datetime; convert to ISO string
                    if isinstance(row_ts, datetime):
                        row_ts = row_ts.isoformat()
                    latest_updated_at = str(row_ts)

            offset += batch_size

        if latest_updated_at:
            state["last_synced_at"] = latest_updated_at
            _save_state(state_path, state)

        logger.info("run_producer.pass_done", published=published,
                    last_synced_at=latest_updated_at)

    def _stop(self, *_):
        logger.info("run_producer.stopping")
        self._running = False
