"""
MQTT adapter for the telemetry queue (PROMPT 082).

Wraps the in-process threading.Queue so it can optionally dual-publish
to an MQTT broker. Consumers (worker threads) always read from the
same queue — no consumer changes required.

When MQTT_ENABLED is False (default, no broker configured), behaviour is
identical to the current queue_worker.py — the adapter is a transparent
passthrough.
"""

import json
import logging
import threading
from queue import Full
from typing import Any, Callable, Dict, Optional

from src.config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC_PREFIX,
    MQTT_ENABLED,
)

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """
    Publisher that writes to an in-process queue and optionally to MQTT.

    Design: publish() always enqueues locally first, then fires to MQTT.
    Workers continue reading from the same queue regardless of MQTT state.
    If the MQTT broker is unreachable at startup, falls back to queue-only
    with a logged warning — no exception is raised to the caller.

    Known limitation: if MQTT is the primary transport and the broker
    goes down mid-session, messages still land in the local queue so
    workers process them. External MQTT subscribers will miss those
    messages until the broker recovers.
    """

    def __init__(self, queue: Optional[threading.Queue] = None) -> None:
        self._queue: threading.Queue = queue if queue is not None else threading.Queue()
        self._mqtt_client = None
        self._connected = False

        if MQTT_ENABLED and MQTT_BROKER_HOST:
            self._init_mqtt()
        else:
            logger.info(
                "MQTTPublisher: in-process queue only "
                "(set MQTT_BROKER_HOST to enable broker publishing)."
            )

    def _init_mqtt(self) -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore

            client = mqtt.Client()
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
            client.loop_start()
            self._mqtt_client = client
            logger.info(
                "MQTTPublisher: connecting to broker at "
                f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}"
            )
        except ImportError:
            logger.warning(
                "paho-mqtt not installed; falling back to queue-only. "
                "Run: pip install paho-mqtt>=1.6.0"
            )
        except Exception as exc:
            logger.warning(
                f"MQTTPublisher: broker connection failed ({exc}); "
                "falling back to queue-only."
            )

    def _on_connect(self, client, userdata, flags, rc: int) -> None:
        if rc == 0:
            self._connected = True
            logger.info("MQTTPublisher: broker connected.")
        else:
            self._connected = False
            logger.warning(f"MQTTPublisher: broker connection refused (rc={rc}).")

    def _on_disconnect(self, client, userdata, rc: int) -> None:
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTTPublisher: unexpected disconnect (rc={rc}).")

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Enqueue the payload locally and, if connected, publish to MQTT.

        Args:
            topic:   Logical sub-topic, e.g. 'telemetry' or 'alerts'.
                     Full MQTT topic becomes {MQTT_TOPIC_PREFIX}/{topic}.
            payload: Dict that will be JSON-serialised for MQTT.

        Returns:
            True if enqueued successfully; False if the queue is full.
        """
        try:
            self._queue.put_nowait((topic, payload))
        except Full:
            logger.warning(f"MQTTPublisher: queue full, dropping message on {topic!r}.")
            return False

        if self._mqtt_client and self._connected:
            try:
                full_topic = f"{MQTT_TOPIC_PREFIX}/{topic}"
                self._mqtt_client.publish(full_topic, json.dumps(payload), qos=0)
            except Exception as exc:
                logger.error(f"MQTTPublisher: MQTT publish failed ({exc}); message already in local queue.")

        return True

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to an MQTT topic.

        When MQTT is disabled, this is a no-op — consumers should read from
        get_queue() directly instead.

        Args:
            topic:    Sub-topic pattern (wildcard # supported if broker allows).
            callback: Called with the decoded payload dict for each message.
        """
        if not (self._mqtt_client and self._connected):
            logger.info(
                f"MQTTPublisher.subscribe: MQTT not connected; "
                f"{topic!r} subscription skipped."
            )
            return

        full_topic = f"{MQTT_TOPIC_PREFIX}/{topic}"

        def _on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode())
                callback(data)
            except Exception as exc:
                logger.error(f"MQTTPublisher: message decode error on {msg.topic}: {exc}")

        self._mqtt_client.subscribe(full_topic)
        self._mqtt_client.on_message = _on_message
        logger.info(f"MQTTPublisher: subscribed to {full_topic!r}")

    def get_queue(self) -> threading.Queue:
        """Return the underlying queue for worker threads."""
        return self._queue

    @property
    def is_mqtt_active(self) -> bool:
        return self._connected and self._mqtt_client is not None


# ------------------------------------------------------------------ #
# Module-level singleton helper
# ------------------------------------------------------------------ #

_default_publisher: Optional[MQTTPublisher] = None


def get_publisher(queue: Optional[threading.Queue] = None) -> MQTTPublisher:
    """Return a module-level singleton publisher, creating it if needed."""
    global _default_publisher
    if _default_publisher is None:
        _default_publisher = MQTTPublisher(queue)
    return _default_publisher


def publish_mqtt_only(self, topic: str, payload: Dict[str, Any]) -> None:
    """Publish to MQTT without touching the internal queue."""
    if self.mqtt_client and self._connected:
        full_topic = f"{MQTT_TOPIC_PREFIX}/{topic}"
        self.mqtt_client.publish(full_topic, json.dumps(payload), qos=0)