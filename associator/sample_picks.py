"""Send three made-up arrivals to Kafka for a local associator check."""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sample_picks(start, now):
    for index in range(3):
        station = f"XX.DEMO{index + 1}"
        pick_time = iso(start + timedelta(seconds=index))
        yield {
            "pick_id": f"{station}:P:{pick_time}:balanced",
            "window_id": f"{station}:{iso(start - timedelta(seconds=30))}",
            "station": station,
            "phase": "P",
            "pick_time": pick_time,
            "probability": 0.9,
            "profile": "balanced",
            "model_version": "phasenet-instance-v2",
            "source": "live",
            "ingested_at": iso(now),
            "picked_at": iso(now),
        }


def publish(picks, bootstrap, replay_offset):
    producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True, "message.timeout.ms": 15000})
    errors = []

    def delivered(error, message):
        if error is not None:
            errors.append(str(error))

    for pick in picks:
        producer.produce(
            "picks",
            key=pick["station"],
            value=json.dumps(pick, allow_nan=False),
            headers={
                "replay_offset_s": str(replay_offset),
                "t_ingested": pick["ingested_at"],
                "t_picked": pick["picked_at"],
            },
            on_delivery=delivered,
        )
    if producer.flush(15) or errors:
        raise RuntimeError(f"Kafka did not acknowledge the sample picks: {errors}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2000-01-01T00:00:00Z", help="First sample arrival in UTC.")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start)
    if start.utcoffset() is None:
        parser.error("--start needs a UTC offset, for example 2000-01-01T00:00:00Z")
    start = start.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    publish(sample_picks(start, now), bootstrap, (now - start).total_seconds() - 3)
    print(f"Kafka acknowledged three sample picks starting at {iso(start)}.")


if __name__ == "__main__":
    main()
