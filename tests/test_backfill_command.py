import signal
import pytest
import pulsar
from django.core.management import call_command
from unittest.mock import patch, MagicMock

from sync.tc_pulsar.consumers.milvus_sync_consumer import MilvusSyncConsumer


pytestmark = pytest.mark.django_db


def test_backfill_uses_earliest_position(settings, monkeypatch):
    settings.PULSAR_NAMESPACE = "testns"
    settings.PULSAR_TENANT = "public"

    captured = {}

    original_init = MilvusSyncConsumer.__init__

    def _capture_init(self, *args, **kwargs):
        captured["consumer_options"] = kwargs.get("consumer_options", {})
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MilvusSyncConsumer, "__init__", _capture_init)
    monkeypatch.setattr(MilvusSyncConsumer, "run", lambda self: None)

    call_command(
        "backfill_milvus",
        subscription="test_backfill_sub",
        topic="attachments",
    )

    assert captured["consumer_options"].get("initial_position") == pulsar.InitialPosition.Earliest


def test_backfill_uses_custom_subscription_name(settings, monkeypatch):
    settings.PULSAR_NAMESPACE = "testns"
    settings.PULSAR_TENANT = "public"

    captured = {}

    original_init = MilvusSyncConsumer.__init__

    def _capture_init(self, *args, **kwargs):
        captured["subscription_name"] = kwargs.get("subscription_name")
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MilvusSyncConsumer, "__init__", _capture_init)
    monkeypatch.setattr(MilvusSyncConsumer, "run", lambda self: None)

    call_command("backfill_milvus", subscription="my_custom_backfill", topic="attachments")

    assert captured["subscription_name"] == "my_custom_backfill"


def test_backfill_uses_custom_topic(settings, monkeypatch):
    settings.PULSAR_NAMESPACE = "testns"
    settings.PULSAR_TENANT = "public"

    captured = {}

    original_init = MilvusSyncConsumer.__init__

    def _capture_init(self, *args, **kwargs):
        captured["consume_topic"] = args[0] if args else kwargs.get("consume_topic")
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MilvusSyncConsumer, "__init__", _capture_init)
    monkeypatch.setattr(MilvusSyncConsumer, "run", lambda self: None)

    call_command("backfill_milvus", subscription="s", topic="test_attachments")

    assert captured["consume_topic"] == "test_attachments"


def test_shutdown_stops_consumer_and_starts_force_exit_timer():
    from sync.management.commands.backfill_milvus import Command

    cmd = Command()
    cmd.consumer = MagicMock()

    with patch("sync.management.commands.backfill_milvus.Timer") as mock_timer:
        mock_timer.return_value = MagicMock()
        cmd._shutdown(signal.SIGTERM, None)

    cmd.consumer.stop.assert_called_once()
    mock_timer.assert_called_once()
    mock_timer.return_value.start.assert_called_once()


def test_shutdown_force_exit_calls_sys_exit():
    from sync.management.commands.backfill_milvus import Command

    cmd = Command()
    cmd.consumer = MagicMock()

    captured = []

    def _capture_timer(delay, fn):
        captured.append(fn)
        return MagicMock()

    with patch("sync.management.commands.backfill_milvus.Timer", side_effect=_capture_timer):
        with patch("sync.management.commands.backfill_milvus.sys") as mock_sys:
            cmd._shutdown(signal.SIGTERM, None)
            captured[0]()  # invoke the force-exit callback directly

    mock_sys.exit.assert_called_once_with(1)
