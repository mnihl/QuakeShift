"""Read picks from Kafka and save detected earthquakes."""

import json
import math
import os
import signal
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import psycopg
from confluent_kafka import Consumer, KafkaException
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from psycopg.rows import dict_row

from .store import save_pick

READY = Event()
STOP = Event()
EVENTS = Counter("quakeshift_events_total", "Earthquakes saved", ("profile", "source"))
LATENCY = Histogram(
    "quakeshift_pipeline_latency_seconds",
    "Time from P-wave arrival to the first live commit",
    ("stage", "profile"),
    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120),
)


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        content_type = "application/json"
        if self.path == "/health":
            status, body = 200, b'{"status":"ok"}'
        elif self.path == "/ready":
            status, body = (200, b'{"status":"ready"}') if READY.is_set() else (503, b'{"status":"starting"}')
        elif self.path == "/metrics":
            status, body = 200, generate_latest()
            content_type = CONTENT_TYPE_LATEST
        else:
            status, body = 404, b'{"status":"not_found"}'

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def utc_now():
    return datetime.now(timezone.utc)


def seconds_since(arrival_time, committed_at):
    if arrival_time is None or arrival_time > committed_at:
        return None
    return (committed_at - arrival_time).total_seconds()


def handle_pick(connection, message):
    pick = json.loads(message.value())
    header = dict(message.headers() or []).get("replay_offset_s")
    offset = float(header) if header is not None else None
    if offset is not None and not math.isfinite(offset):
        offset = None

    result = save_pick(connection, pick, offset)
    committed_at = utc_now()
    profile = pick["profile"]
    source = pick["source"]
    record = {
        "timestamp": committed_at.isoformat(),
        "service": "associator",
        "profile": profile,
        "source": source,
        "window_id": pick["window_id"],
        "action": result.action,
    }

    if result.action == "inserted":
        EVENTS.labels(profile, source).inc()
        if source == "live":
            latency = seconds_since(result.first_p_wall, committed_at)
            after_third = seconds_since(result.third_p_wall, committed_at)
            if latency is not None:
                # The acknowledgement time is available only after the event commit.
                connection.execute(
                    "UPDATE events SET pipeline_latency_s = %s WHERE id = %s",
                    (latency, result.event_id),
                )
                LATENCY.labels("end_to_end", profile).observe(latency)
            if after_third is not None:
                LATENCY.labels("after_third_station", profile).observe(after_third)
            record.update(
                pipeline_latency_s=latency,
                after_third_station_s=after_third,
                ingested_at=pick["ingested_at"],
                picked_at=pick["picked_at"],
            )

    if result.action in ("inserted", "updated", "overlap_review"):
        record.update(event_id=result.event_id)
        if result.conflicts:
            record["conflicting_event_ids"] = result.conflicts
        print(json.dumps(record), flush=True)


def main():
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    port = int(os.environ.get("METRICS_PORT", "9100"))
    dsn = os.environ.get("POSTGRES_DSN", "postgresql://quakeshift:quakeshift@localhost:5432/quakeshift")
    consumer = Consumer({
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092"),
        "group.id": "associator",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
    })

    try:
        with ThreadingHTTPServer(("", port), StatusHandler) as server:
            Thread(target=server.serve_forever, daemon=True).start()
            with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as connection:
                connection.execute("SELECT 1 FROM association_picks LIMIT 0")
                if "picks" not in consumer.list_topics(timeout=10).topics:
                    raise RuntimeError("The Kafka topic 'picks' is missing. Run the topic setup first.")
                consumer.subscribe(["picks"])
                READY.set()
                while not STOP.is_set():
                    message = consumer.poll(1)
                    if message is None:
                        continue
                    if message.error() is not None:
                        raise KafkaException(message.error())
                    handle_pick(connection, message)
                    # Pending picks are already durable, even before they form an event.
                    for offset in consumer.commit(message=message, asynchronous=False):
                        if offset.error is not None:
                            raise KafkaException(offset.error)
    finally:
        READY.clear()
        consumer.close()


if __name__ == "__main__":
    main()
