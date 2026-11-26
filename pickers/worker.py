"""Kafka live picker worker, backfill Job runner, and /health /ready /metrics server.

Live mode:     PICKER_PROFILE=balanced KAFKA_BOOTSTRAP=localhost:19092 python -m pickers.worker
Backfill mode: BACKFILL_START=... BACKFILL_END=... python -m pickers.worker --mode backfill
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from obspy import UTCDateTime
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from pickers.phasenet import format_utc_ms
from pickers.profiles import create_picker

LATENCY_BUCKETS = (1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120)
PICKS_TOTAL = Counter(
    "quakeshift_picks_total", "Total seismic wave picks produced.",
    ["station", "phase", "profile", "source"],
)
STAGE_LATENCY = Histogram(
    "quakeshift_pipeline_latency_seconds", "Pipeline latency seconds by stage and profile.",
    ["stage", "profile"], buckets=LATENCY_BUCKETS,
)


def log_json(service: str, profile: str, **fields: Any) -> None:
    record = {"timestamp": format_utc_ms(UTCDateTime()), "service": service, "profile": profile, **fields}
    print(json.dumps(record, separators=(",", ":")), flush=True)


def start_probe_server(port: int, ready_event: threading.Event) -> ThreadingHTTPServer:
    """Serve /health, /ready, and /metrics on `port` in a background daemon thread."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/health":
                code, ctype, body = 200, "application/json", b'{"status":"ok"}'
            elif path == "/ready":
                ready = ready_event.is_set()
                code, ctype, body = (200, "application/json", b'{"status":"ready"}') if ready else (503, "application/json", b'{"status":"not ready"}')
            elif path == "/metrics":
                code, ctype, body = 200, CONTENT_TYPE_LATEST, generate_latest()
            else:
                code, ctype, body = 404, "application/json", b'{"error":"not found"}'
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def process_window_message(
    window_or_raw: dict[str, Any] | bytes | str,
    picker: Any,
    producer: Any,
    *,
    source: str = "live",
    picks_topic: str = "picks",
) -> list[dict[str, Any]]:
    """Run picker on one `waveforms` window, produce picks to Kafka, flush, and record metrics."""
    window = (
        window_or_raw
        if isinstance(window_or_raw, dict)
        else json.loads(window_or_raw.decode("utf-8") if isinstance(window_or_raw, bytes) else window_or_raw)
    )
    if window.get("ingested_at"):
        queue_s = max(0.0, time.time() - UTCDateTime(window["ingested_at"]).timestamp)
        STAGE_LATENCY.labels(stage="queue", profile=picker.profile).observe(queue_s)

    t0 = time.perf_counter()
    picks = picker.pick_window(window, source=source)
    STAGE_LATENCY.labels(stage="inference", profile=picker.profile).observe(time.perf_counter() - t0)

    failures: list[str] = []
    replay_offset = str(float(window.get("replay_offset_s", 0.0)))
    for pick in picks:
        producer.produce(
            picks_topic,
            key=pick["station"],
            value=json.dumps(pick, separators=(",", ":"), allow_nan=False),
            headers={
                "t_ingested": pick["ingested_at"],
                "t_picked": pick["picked_at"],
                "replay_offset_s": replay_offset,
            },
            on_delivery=lambda err, _: failures.append(str(err)) if err is not None else None,
        )

    if picks:
        pending = producer.flush(15)
        if failures:
            raise RuntimeError(f"Kafka pick delivery failed: {failures[0]}")
        if pending:
            raise RuntimeError(f"Kafka did not acknowledge {pending} pick message(s)")
        for pick in picks:
            PICKS_TOTAL.labels(
                station=pick["station"], phase=pick["phase"], profile=pick["profile"], source=pick["source"],
            ).inc()

    log_json(
        service="backfill-job" if source == "backfill" else f"picker-{picker.profile}",
        profile=picker.profile,
        window_id=window["window_id"],
        picks=len(picks),
        source=source,
    )
    return picks


def window_overlaps_period(window: dict[str, Any], period_start: UTCDateTime, period_end: UTCDateTime) -> bool:
    """Return True if the recorded waveform window overlaps [period_start, period_end)."""
    return UTCDateTime(window["window_end"]) > period_start and UTCDateTime(window["window_start"]) < period_end


def _make_kafka_clients(bootstrap: str, group_id: str, client_id: str):
    from confluent_kafka import Consumer, Producer

    producer = Producer({
        "bootstrap.servers": bootstrap,
        "client.id": client_id,
        "enable.idempotence": True,
        "message.timeout.ms": 15000,
    })
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    return consumer, producer


def run_live(
    bootstrap: str, profile: str, *, ready_event: threading.Event, stop_event: threading.Event,
) -> None:
    picker = create_picker(profile, source="live")
    consumer, producer = _make_kafka_clients(bootstrap, "live-pickers", f"picker-{profile}")
    if "waveforms" not in producer.list_topics(timeout=10).topics:
        raise RuntimeError("Kafka topic 'waveforms' is missing.")
    consumer.subscribe(["waveforms"])
    ready_event.set()
    log_json(f"picker-{profile}", profile, event="ready", kafka=bootstrap)

    try:
        while not stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise RuntimeError(f"Kafka consumer error: {msg.error()}")
            process_window_message(msg.value(), picker, producer, source="live")
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()
        producer.flush(10)


def run_backfill(bootstrap: str, start_iso: str, end_iso: str, *, ready_event: threading.Event) -> int:
    from confluent_kafka import TopicPartition

    period_start, period_end = UTCDateTime(start_iso), UTCDateTime(end_iso)
    picker = create_picker("performance", source="backfill")
    consumer, producer = _make_kafka_clients(bootstrap, "backfill", "backfill-job")
    meta = consumer.list_topics("waveforms", timeout=10)
    if "waveforms" not in meta.topics:
        raise RuntimeError("Kafka topic 'waveforms' is missing.")

    start_ms = int(period_start.timestamp * 1000)
    targets: dict[int, int] = {}
    assignments = []
    for pid in meta.topics["waveforms"].partitions:
        low, high = consumer.get_watermark_offsets(TopicPartition("waveforms", pid), timeout=10)
        if high <= low:
            continue
        targets[pid] = high
        # Seek to BACKFILL_START by broker time when available; fall back to `low` for historical replays.
        looked_up = consumer.offsets_for_times([TopicPartition("waveforms", pid, start_ms)], timeout=10)[0]
        assignments.append(TopicPartition("waveforms", pid, looked_up.offset if looked_up.offset >= low else low))

    ready_event.set()
    if not assignments:
        consumer.close()
        return 0

    consumer.assign(assignments)
    total_picks, empty_polls = 0, 0
    try:
        while targets and empty_polls < 5:
            msg = consumer.poll(1.0)
            if msg is None:
                empty_polls += 1
                continue
            empty_polls = 0
            if msg.error():
                raise RuntimeError(f"Kafka backfill consumer error: {msg.error()}")
            window = json.loads(msg.value().decode("utf-8"))
            if window_overlaps_period(window, period_start, period_end):
                total_picks += len(process_window_message(window, picker, producer, source="backfill"))
            consumer.commit(message=msg, asynchronous=False)
            pid = msg.partition()
            if pid in targets and msg.offset() + 1 >= targets[pid]:
                del targets[pid]
    finally:
        consumer.close()
        producer.flush(10)
    return total_picks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QuakeShift live picker worker or backfill job.")
    parser.add_argument("--mode", choices=("live", "backfill"), default=os.environ.get("PICKER_MODE", "live"))
    parser.add_argument("--profile", default=os.environ.get("PICKER_PROFILE", "balanced"))
    parser.add_argument("--start", default=os.environ.get("BACKFILL_START"))
    parser.add_argument("--end", default=os.environ.get("BACKFILL_END"))
    args = parser.parse_args()

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:19092")
    metrics_port = int(os.environ.get("METRICS_PORT", "9100"))
    ready_event, stop_event = threading.Event(), threading.Event()
    server = start_probe_server(metrics_port, ready_event)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: stop_event.set())
        except ValueError:
            pass

    try:
        if args.mode == "backfill":
            if not args.start or not args.end:
                raise SystemExit("Backfill mode requires BACKFILL_START and BACKFILL_END (or --start/--end).")
            total = run_backfill(bootstrap, args.start, args.end, ready_event=ready_event)
            log_json("backfill-job", "performance", event="done", total_picks=total)
        else:
            run_live(bootstrap, args.profile, ready_event=ready_event, stop_event=stop_event)
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
