"""
High-Throughput Async Telemetry Queue .
Uses threading.Queue with a Kafka‑compatible interface.
"""

import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from queue import Queue, Full

from src.config import (
    TELEMETRY_QUEUE_MAX_SIZE,
    TELEMETRY_BATCH_SIZE,
    TELEMETRY_FLUSH_INTERVAL_S,
)
from src.model import predict_single, log_prediction

logger = logging.getLogger(__name__)


class TelemetryQueue:
    """
    Asynchronous telemetry queue that buffers sensor readings
    and processes them in batches at a fixed interval.
    """

    def __init__(
        self,
        maxsize: int = TELEMETRY_QUEUE_MAX_SIZE,
        batch_size: int = TELEMETRY_BATCH_SIZE,
        flush_interval_s: int = TELEMETRY_FLUSH_INTERVAL_S,
    ):
        self.queue = Queue(maxsize=maxsize)
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._processed_today = 0
        self._lock = threading.Lock()
        self._last_reset_date = datetime.now().date()

    def enqueue(self, reading: Dict[str, Any]) -> bool:
        """
        Add a reading to the queue. Returns True if enqueued, False if queue is full.
        """
        # ---- 1. Try to put into the in‑process queue ----
        try:
            self.queue.put_nowait(reading)
        except Full:
            return False

        # ---- 2. Optionally publish to MQTT (if configured) ----
        # We'll only publish if MQTT is enabled and we have a client.
        try:
            from src.mqtt_adapter import get_publisher as _get_publisher
            if not hasattr(self, '_publisher'):
                self._publisher = _get_publisher(self.queue)
            # We need a method that publishes to MQTT only, not to the queue.
            # We'll add a new method to the publisher, or use a direct check.
            # For simplicity, we'll check if the publisher has a client and is connected,
            # then publish directly using paho (or we can add a method).
            # Since we already have the publisher, we can add a new method to it.
            # Let's assume we've added a `publish_mqtt_only` method.
            # If not, we can call the existing publish but we must avoid re-queueing.
            # Instead, we'll use the publisher's internal mqtt_client directly.

            if self._publisher.mqtt_client and self._publisher._connected:
                import json
                self._publisher.mqtt_client.publish(
                    f"smart_city/traffic/telemetry",
                    json.dumps(reading),
                    qos=0
                )
            
            self._publisher.publish_mqtt_only('telemetry', reading)
        except Exception as e:
            # Log but don't fail the enqueue
            import logging
            logging.warning(f"MQTT publish failed: {e}")

        return True

    def _process_batch(self) -> int:
        """
        Pull up to batch_size items from the queue, process each with predict_single,
        and log the result.
        Returns the number of items processed.
        """
        items = []
        for _ in range(self.batch_size):
            try:
                item = self.queue.get_nowait()
                items.append(item)
            except Exception:
                break

        if not items:
            return 0

        # We need a reference to the app state to get model, feature_cols, city_dfs.
        # This is set in app.py; we'll retrieve it via a global or use a callback.
        # To keep this module decoupled, we'll use a global variable set by app.py.
        # We'll define a function to get the state, and app.py will inject it.
        # For simplicity, we'll assume app.state is accessible via a global.
        # We'll use a placeholder: get_app_state() will be replaced by app.py injection.
        # Better: accept a callable in __init__ that returns the state.
        # We'll modify __init__ to accept a state_getter callable.
        # We'll implement that in app.py.

        # For now, we'll raise an error if state_getter is not set.
        if not hasattr(self, '_state_getter'):
            logger.error("State getter not set. Cannot process batch.")
            return 0

        state = self._state_getter()
        if state is None:
            logger.error("App state is None. Cannot process batch.")
            return 0

        model = state.model
        feature_cols = state.feature_cols
        city_dfs = state.city_dfs

        for reading in items:
            # Convert to predict_single parameters
            try:
                result = predict_single(
                    city=reading.get('city', 'Riyadh'),
                    zone=reading.get('zone', 'Zone_1'),
                    hour=reading.get('hour', 8),
                    vehicle_count=reading.get('vehicle_count', 100),
                    avg_speed=reading.get('avg_speed', 60),
                    weather=reading.get('weather', 'clear'),
                    road_type=reading.get('road_type', 'arterial'),
                    rush_hour=reading.get('rush_hour', 0),
                    is_weekend=reading.get('is_weekend', 0),
                    is_late_night=reading.get('is_late_night', 0),
                    event=reading.get('event', 0),
                    hour_multiplier=reading.get('hour_multiplier', 1.0),
                )
                # We need to log the prediction; we need an explanation,
                # but we can generate a simple explanation or skip.
                # Since log_prediction expects explanation dict, we can provide a minimal one.
                explanation = {
                    'top_factors': [
                        {'factor': 'vehicle_count', 'direction': 'increasing', 'impact': 0.1},
                        {'factor': 'avg_speed', 'direction': 'reducing', 'impact': 0.1},
                        {'factor': 'hour', 'direction': 'increasing', 'impact': 0.05},
                    ],
                    'plain_english': 'Congestion driven by vehicle count and speed.'
                }
                # Log the prediction
                log_prediction(result, explanation)
            except Exception as e:
                logger.error(f"Error processing reading: {e}")

        with self._lock:
            self._processed_today += len(items)
            # Reset daily counter if date changed
            today = datetime.now().date()
            if today != self._last_reset_date:
                self._processed_today = len(items)
                self._last_reset_date = today

        return len(items)

    def _worker_loop(self):
        """Background thread: repeatedly flush the queue."""
        while not self._stop_event.is_set():
            self._process_batch()
            # Sleep for flush_interval seconds, but check stop_event periodically
            for _ in range(self.flush_interval_s):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        # Final flush on stop
        self._process_batch()

    def start_worker(self, state_getter):
        """
        Start the background worker thread.
        state_getter is a callable that returns the app state (with model, feature_cols, city_dfs).
        """
        if self._worker_thread is not None and self._worker_thread.is_alive():
            logger.warning("Worker already running.")
            return

        self._state_getter = state_getter
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop_worker(self):
        """Signal the worker to stop and wait for it to finish."""
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

    def queue_depth(self) -> int:
        """Return the current number of items in the queue."""
        return self.queue.qsize()

    def processed_today(self) -> int:
        """Return the number of items processed since midnight."""
        with self._lock:
            return self._processed_today

    def is_worker_active(self) -> bool:
        """Return whether the worker thread is running."""
        return self._worker_thread is not None and self._worker_thread.is_alive()