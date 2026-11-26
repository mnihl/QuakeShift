"""Tests for eco/performance profiles, Kafka message handling, backfill filtering, and probes."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from obspy import UTCDateTime

from ingestor.replay import replay_windows
from pickers.phasenet import PhaseNetPicker, deduplicate_picks, find_p_cluster
from pickers.profiles import EQT_MODEL_VERSION, EcoPicker, EQTransformerPicker, create_picker
from pickers.worker import process_window_message, start_probe_server, window_overlaps_period


class _FakeProducer:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.flushed = 0

    def produce(self, topic, *, key, value, headers, on_delivery):
        self.sent.append({"topic": topic, "key": key, "value": json.loads(value), "headers": headers})
        on_delivery(None, None)

    def flush(self, timeout: float = 15) -> int:
        self.flushed += 1
        return 0


def _window(station: str = "IV.ATVO", peak: float = 0.0) -> dict:
    z = [0.0] * 6000
    if peak:
        z[3500:3650] = [peak] * 150
    return {
        "window_id": f"{station}:2023-03-09T19:07:16Z",
        "station": station,
        "sample_rate_hz": 100,
        "window_start": "2023-03-09T19:07:16Z",
        "window_end": "2023-03-09T19:08:16Z",
        "channels": {"Z": z, "N": [0.0] * 6000, "E": [0.0] * 6000},
        "ingested_at": "2026-11-26T20:00:00.120Z",
        "replay_offset_s": 500.0,
    }


def test_eco_picker_filters_stations_and_gates_with_stalta() -> None:
    calls = 0

    def fake_classify(stream):
        nonlocal calls
        calls += 1
        return SimpleNamespace(picks=[SimpleNamespace(phase="P", peak_time=UTCDateTime("2023-03-09T19:08:08.7Z"), peak_value=0.9)])

    pn = PhaseNetPicker(profile="eco", model=SimpleNamespace(classify=fake_classify))
    eco = EcoPicker(core_stations="IV.ATVO,IV.ATMI,IV.ATFO", threshold=5.0, phasenet=pn)

    assert eco.pick_window(_window("IV.APEC", peak=100.0)) == []  # non-core station skipped
    assert eco.pick_window(_window("IV.ATVO", peak=0.0)) == []    # quiet window skipped
    assert calls == 0

    picks = eco.pick_window(_window("IV.ATVO", peak=100.0))
    assert calls == 1
    assert len(picks) == 1 and picks[0]["profile"] == "eco"


def test_eqtransformer_picker_emits_performance_version_and_backfill_source() -> None:
    fake_model = SimpleNamespace(
        classify=lambda s: SimpleNamespace(
            picks=[SimpleNamespace(phase="P", peak_time=UTCDateTime("2023-03-09T19:08:08.7Z"), peak_value=0.95)]
        )
    )
    eqt = EQTransformerPicker(profile="performance", source="backfill", model=fake_model)
    picks = eqt.pick_window(_window("IV.ATVO"))
    assert len(picks) == 1
    assert picks[0]["model_version"] == EQT_MODEL_VERSION
    assert picks[0]["profile"] == "performance"
    assert picks[0]["source"] == "backfill"


def test_process_window_message_produces_contract_headers_and_flushes() -> None:
    fake_model = SimpleNamespace(
        classify=lambda s: SimpleNamespace(
            picks=[SimpleNamespace(phase="P", peak_time=UTCDateTime("2023-03-09T19:08:08.7Z"), peak_value=0.92)]
        )
    )
    picker = PhaseNetPicker(profile="balanced", model=fake_model)
    producer = _FakeProducer()
    raw = json.dumps(_window("IV.ATVO")).encode("utf-8")

    picks = process_window_message(raw, picker, producer, source="live")
    assert len(picks) == 1
    assert producer.flushed == 1
    sent = producer.sent[0]
    assert sent["topic"] == "picks"
    assert sent["key"] == "IV.ATVO"
    assert sent["headers"]["t_ingested"] == "2026-11-26T20:00:00.120Z"
    assert sent["headers"]["replay_offset_s"] == "500.0"
    assert "t_picked" in sent["headers"]


def test_window_overlaps_period() -> None:
    w = _window()
    assert window_overlaps_period(w, UTCDateTime("2023-03-09T19:08:00Z"), UTCDateTime("2023-03-09T19:09:00Z"))
    assert not window_overlaps_period(w, UTCDateTime("2023-03-09T19:08:16Z"), UTCDateTime("2023-03-09T19:09:00Z"))


def test_probe_server_health_ready_and_metrics() -> None:
    ready = threading.Event()
    server = start_probe_server(0, ready)
    port = server.server_address[1]
    try:
        with urlopen(f"http://127.0.0.1:{port}/health") as r:
            assert r.status == 200 and json.loads(r.read()) == {"status": "ok"}

        with pytest.raises(HTTPError) as exc:
            urlopen(f"http://127.0.0.1:{port}/ready")
        assert exc.value.code == 503

        ready.set()
        with urlopen(f"http://127.0.0.1:{port}/ready") as r:
            assert r.status == 200 and json.loads(r.read()) == {"status": "ready"}

        with urlopen(f"http://127.0.0.1:{port}/metrics") as r:
            body = r.read().decode("utf-8")
            assert r.status == 200
            assert "quakeshift_picks_total" in body
            assert "quakeshift_pipeline_latency_seconds" in body
    finally:
        server.shutdown()


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data/raw/umbertide_20230309.mseed").exists(),
    reason="Run python scripts/download_replay.py first",
)
@pytest.mark.parametrize("profile", ["eco", "performance"])
def test_eco_and_performance_detect_umbertide_three_core_stations(profile: str) -> None:
    picker = create_picker(profile, core_stations="IV.ATVO,IV.ATMI,IV.ATFO")
    picks = [p for w in replay_windows("umbertide") for p in picker.pick_window(w)]
    cluster = find_p_cluster(deduplicate_picks(picks))
    assert {"IV.ATVO", "IV.ATMI", "IV.ATFO"}.issubset({p["station"] for p in cluster})
