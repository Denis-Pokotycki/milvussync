"""
In-memory fake Pulsar client for tests.

Implements only the subset of the Pulsar Python API used in the app:
- Client.create_producer
- Client.subscribe
- Producer.send
- Consumer.receive/acknowledge/negative_acknowledge/is_connected/close
- Message.value/data/message_id/redelivery_count

Use via pytest fixture in tests/conftest.py which patches pulsar.Client
to FakeClient and resets the broker between tests.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

try:
    # We raise the real Timeout to keep app code behavior identical
    import pulsar as _real_pulsar  # type: ignore
    PulsarTimeout = _real_pulsar.Timeout
except Exception:  # pragma: no cover - fallback if package missing
    class PulsarTimeout(TimeoutError):
        pass


class _TopicQueue:
    def __init__(self) -> None:
        self.queue: Deque[FakeMessage] = deque()
        self.lock = threading.Lock()

    def push(self, msg: "FakeMessage") -> None:
        with self.lock:
            self.queue.append(msg)

    def pushleft(self, msg: "FakeMessage") -> None:
        with self.lock:
            self.queue.appendleft(msg)

    def pop(self) -> Optional["FakeMessage"]:
        with self.lock:
            return self.queue.popleft() if self.queue else None


class _Broker:
    def __init__(self) -> None:
        self._topics: Dict[str, _TopicQueue] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._topics.clear()

    def get_topic(self, name: str) -> _TopicQueue:
        with self._lock:
            if name not in self._topics:
                self._topics[name] = _TopicQueue()
            return self._topics[name]

    def send(self, topic: str, content: Any) -> "FakeMessageId":
        msg = FakeMessage(content=content)
        self.get_topic(topic).push(msg)
        return msg.message_id()


broker = _Broker()


@dataclass
class FakeMessageId:
    id: str

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return self.id


class FakeMessage:
    def __init__(self, content: Any, redelivery_count: int = 0) -> None:
        self._content = content
        self._id = FakeMessageId(str(uuid.uuid4()))
        self._redelivery_count = redelivery_count

    def value(self) -> Any:
        return self._content

    def data(self) -> bytes:
        """Support message.data() calls in consumers that skip schema deserialization."""
        if isinstance(self._content, bytes):
            return self._content
        return json.dumps(self._content).encode("utf-8")

    # Some code uses message.message_id() as a key
    def message_id(self) -> FakeMessageId:
        return self._id

    def redelivery_count(self) -> int:
        return self._redelivery_count

    # Compatibility with code that might log the message
    def __repr__(self) -> str:  # pragma: no cover - for debugging
        return f"<FakeMessage id={self._id} redelivery={self._redelivery_count}>"


class FakeProducer:
    def __init__(self, topic: str, **_: Any) -> None:
        self._topic = topic
        self._closed = False

    def send(self, content: Any, **__: Any) -> FakeMessageId:
        if self._closed:
            raise RuntimeError("Producer is closed")
        return broker.send(self._topic, content)

    def close(self) -> None:
        self._closed = True


class FakeConsumer:
    def __init__(self, topic: str, **_: Any) -> None:
        self._topic = topic
        self._connected = True
        # Track pending messages to support negative_acknowledge
        self._pending: Dict[str, FakeMessage] = {}

    def receive(self, timeout_millis: Optional[int] = None) -> FakeMessage:
        deadline = None
        if timeout_millis is not None and timeout_millis >= 0:
            deadline = time.monotonic() + (timeout_millis / 1000.0)

        while True:
            msg = broker.get_topic(self._topic).pop()
            if msg is not None:
                self._pending[msg.message_id().id] = msg
                return msg

            if deadline is not None and time.monotonic() >= deadline:
                raise PulsarTimeout()

            # Sleep a tiny amount to avoid busy-wait
            time.sleep(0.001)

    def acknowledge(self, message: FakeMessage) -> None:
        self._pending.pop(message.message_id().id, None)

    def negative_acknowledge(self, message: FakeMessage) -> None:
        # Requeue for redelivery
        mid = message.message_id().id
        orig = self._pending.pop(mid, None)
        if orig is not None:
            redelivered = FakeMessage(orig.value(), redelivery_count=orig.redelivery_count() + 1)
            broker.get_topic(self._topic).pushleft(redelivered)

    def is_connected(self) -> bool:
        return self._connected

    def close(self) -> None:
        self._connected = False


class FakeClient:
    def __init__(self, **__: Any) -> None:
        self._closed = False

    def create_producer(self, **kwargs: Any) -> FakeProducer:
        if self._closed:
            raise RuntimeError("Client is closed")
        topic = kwargs.pop("topic", None)
        if not topic:
            raise ValueError("create_producer requires 'topic'")
        return FakeProducer(topic=topic, **kwargs)

    def subscribe(self, **kwargs: Any) -> FakeConsumer:
        if self._closed:
            raise RuntimeError("Client is closed")
        topic = kwargs.pop("topic", None)
        if not topic:
            raise ValueError("subscribe requires 'topic'")
        return FakeConsumer(topic=topic, **kwargs)

    def close(self) -> None:
        self._closed = True
