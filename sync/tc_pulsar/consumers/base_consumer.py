import contextlib
import os
import uuid
import pulsar
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from django.conf import settings
from milvussync.logging import get_logger


class BasePulsarConsumer(ABC):

    def __init__(
        self,
        consume_topic: str,
        schema: pulsar.schema.Schema = None,
        subscription_name: str = "",
        consumer_type: pulsar.ConsumerType = pulsar.ConsumerType.Shared,
        client_options: Optional[Dict[str, Any]] = None,
        consumer_options: Optional[Dict[str, Any]] = None,
        do_not_ack_negative: bool = False
    ):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.topic = consume_topic
        self.subscription_name = subscription_name or f"{settings.DJANGO_ENVIRONMENT}_{self.__class__.__name__}_subscription"
        self.schema = schema
        self.consumer_type = consumer_type
        self.do_not_ack_negative = do_not_ack_negative
        self.pulsar_namespace = settings.PULSAR_NAMESPACE
        self.pulsar_tenant = settings.PULSAR_TENANT

        # Default client options
        self._client_options = {
            'service_url': settings.PULSAR_URL,
            'operation_timeout_seconds': 10,
            'logger': pulsar.ConsoleLogger(pulsar.LoggerLevel.Error),
        }

        if client_options:
            self._client_options |= client_options

        # Default consumer options
        self._consumer_options = {
            'topic': self.build_topic_name(self.topic),
            'subscription_name': self.subscription_name,
            'consumer_type': self.consumer_type,
            'consumer_name': self._create_unique_name(),
            'dead_letter_policy': pulsar.ConsumerDeadLetterPolicy(
                max_redeliver_count=3,
                dead_letter_topic=self.build_dead_letter_topic_name(self.topic),
            ),
        }

        if consumer_options:
            self._consumer_options |= consumer_options
        if self.schema:
            self._consumer_options['schema'] = self.schema

        self.client = None
        self.consumer = None

        self._running = False
        self._stop_event = None

    def set_stop_event(self, event):
        self._stop_event = event

    def build_topic_name(self, topic):
        return f"{self.pulsar_tenant}/{self.pulsar_namespace}/{topic}"

    def build_dead_letter_topic_name(self, topic):
        return self.build_topic_name(f"{topic}-DLQ")

    def connect(self) -> None:
        if not self.consumer:
            try:
                self.client = pulsar.Client(**self._client_options)
                self.consumer = self.client.subscribe(**self._consumer_options)
                self.logger.info(f"Connected to Pulsar topic: {self.topic}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Pulsar: {str(e)}")
                self.logger.error(e)
                raise

    def disconnect(self) -> None:
        try:
            if self.consumer:
                self.consumer.close()
            if self.client:
                self.client.close()
            self.logger.info("Disconnected from Pulsar")
        except Exception as e:
            self.logger.error(f"Error disconnecting from Pulsar: {str(e)}")
            self.logger.error(e)
        finally:
            self.consumer = None
            self.client = None

    def run(self) -> None:
        self.before_run()
        try:
            self.connect()
        except Exception as e:
            self.logger.error(f"Failed to connect to Pulsar: {str(e)}")
            return
        self.logger.info(f"Starting to consume messages from {self.topic}")
        self._running = True
        message = None

        while self.is_running():
            message = self.consume()
        self.after_run(message)
        self.disconnect()

    def consume(self) -> pulsar.Message | None:
        message = None
        try:
            with contextlib.suppress(pulsar.Timeout):
                message = self.consumer.receive(timeout_millis=1000)
                self.process_message(message)
                self.consumer.acknowledge(message)
                self.logger.debug(f"Message processed: {message}")
        except Exception as e:
            self.logger.exception(e)
            if message is not None and not self.do_not_ack_negative:
                self.consumer.negative_acknowledge(message)
        return message

    def stop(self) -> None:
        self._running = False

    @abstractmethod
    def process_message(self, message) -> Any:
        pass

    def before_run(self) -> None:
        pass

    def after_run(self, message) -> None:
        pass

    def healthcheck(self) -> bool:
        return self.consumer.is_connected() if self.consumer else False

    def is_running(self):
        return self._running and (self._stop_event is None or not self._stop_event.is_set())

    def _create_unique_name(self):
        hostname = os.environ.get("HOSTNAME", "unknown-host")
        unique_id = uuid.uuid4().hex[:6]
        return f"consumer-{settings.DJANGO_ENVIRONMENT}-{hostname}-{unique_id}"
