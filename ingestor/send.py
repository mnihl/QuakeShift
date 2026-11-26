"""Replay a recording into Kafka at its original speed."""

import argparse
import json
import os
import time
from datetime import datetime, timezone

from confluent_kafka import Producer

from scripts.download_replay import CLIPS

from .replay import replay_windows


def send_replay(clip, bootstrap):
    producer = Producer({
        "bootstrap.servers": bootstrap,
        "client.id": "ingestor",
        "enable.idempotence": True,
        "compression.type": "lz4",
        "message.timeout.ms": 15000,
    })
    if "waveforms" not in producer.list_topics(timeout=10).topics:
        raise RuntimeError("The Kafka topic 'waveforms' is missing. Run the topic setup first.")

    failures = []

    def check_delivery(error, message):
        if error is not None:
            failures.append(f"{message.key().decode()}: {error}")

    clip_start = datetime.fromisoformat(CLIPS[clip]["start_time"]).replace(tzinfo=timezone.utc)
    replay_start = time.monotonic()
    replay_offset = time.time() - clip_start.timestamp()
    count = 0

    for window in replay_windows(clip):
        window_end = datetime.fromisoformat(window["window_end"])
        seconds_into_clip = (window_end - clip_start).total_seconds()
        # Wait until the end of the trailing window reaches the replay clock.
        wait_seconds = replay_start + seconds_into_clip - time.monotonic()
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        producer.poll(0)
        if failures:
            raise RuntimeError(f"Kafka delivery failed for {failures[0]}")

        ingested_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        window["ingested_at"] = ingested_at
        window["replay_offset_s"] = replay_offset
        producer.produce(
            "waveforms",
            key=window["station"],
            value=json.dumps(window, separators=(",", ":"), allow_nan=False),
            headers={"t_ingested": ingested_at},
            on_delivery=check_delivery,
        )
        count += 1

    pending = producer.flush(15)
    if failures:
        raise RuntimeError(f"Kafka delivery failed for {failures[0]}")
    if pending:
        raise RuntimeError(f"Kafka did not acknowledge {pending} waveform windows")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", choices=CLIPS, nargs="?", default="umbertide")
    clip = parser.parse_args().clip
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    print(f"Replaying {clip} at 1×. The first windows are sent after 60 seconds.", flush=True)
    print(f"Kafka acknowledged {send_replay(clip, bootstrap)} waveform windows.")


if __name__ == "__main__":
    main()
