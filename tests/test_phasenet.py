"""Tests for the PhaseNet balanced picker."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from obspy import UTCDateTime

from ingestor.replay import replay_windows
from pickers.phasenet import (
    MODEL_VERSION,
    PhaseNetPicker,
    build_stream,
    deduplicate_picks,
    find_p_cluster,
    format_utc_ms,
)

REQUIRED_PICK_KEYS = {
    "pick_id", "window_id", "station", "phase", "pick_time",
    "probability", "profile", "model_version", "source", "ingested_at", "picked_at",
}


def _sample_window(n: int = 6000) -> dict:
    return {
        "window_id": "IV.ATVO:2023-03-09T19:07:16Z",
        "station": "IV.ATVO",
        "sample_rate_hz": 100,
        "window_start": "2023-03-09T19:07:16Z",
        "window_end": "2023-03-09T19:08:16Z",
        "channels": {"Z": [0.0] * n, "N": [0.1] * n, "E": [-0.1] * n},
        "ingested_at": "2026-11-26T20:00:00.120Z",
    }


def test_format_utc_ms_rounds_cleanly() -> None:
    assert format_utc_ms("2023-03-09T19:08:09.9996Z") == "2023-03-09T19:08:10.000Z"


def test_build_stream_creates_three_100hz_traces() -> None:
    stream = build_stream(_sample_window())
    assert [tr.stats.channel for tr in stream] == ["HHZ", "HHN", "HHE"]
    assert all(tr.stats.sampling_rate == 100.0 and len(tr.data) == 6000 for tr in stream)


def test_pick_window_matches_contracts_format() -> None:
    fake_picks = [
        SimpleNamespace(phase="S", peak_time=UTCDateTime("2023-03-09T19:08:11.25Z"), peak_value=0.84216),
        SimpleNamespace(phase="P", peak_time=UTCDateTime("2023-03-09T19:08:08.53Z"), peak_value=0.91344),
        SimpleNamespace(phase="P", peak_time=UTCDateTime("2023-03-09T19:08:16.00Z"), peak_value=0.99),  # exclusive end
    ]
    fake_model = SimpleNamespace(classify=lambda stream: SimpleNamespace(picks=fake_picks))
    picker = PhaseNetPicker(profile="balanced", model=fake_model)

    picks = picker.pick_window(_sample_window(), picked_at="2026-11-26T20:00:01.450Z")
    assert [p["phase"] for p in picks] == ["P", "S"]
    assert all(set(p.keys()) == REQUIRED_PICK_KEYS for p in picks)
    assert picks[0]["pick_id"] == "IV.ATVO:P:2023-03-09T19:08:08.530Z:balanced"
    assert picks[0]["model_version"] == MODEL_VERSION
    assert picks[0]["probability"] == 0.9134


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data/raw/umbertide_20230309.mseed").exists(),
    reason="Run python scripts/download_replay.py first",
)
def test_umbertide_replay_detects_three_core_p_waves_within_10s() -> None:
    picker = PhaseNetPicker(profile="balanced")
    all_picks = [p for w in replay_windows("umbertide") for p in picker.pick_window(w)]
    assert all(set(p.keys()) == REQUIRED_PICK_KEYS for p in all_picks)

    cluster = find_p_cluster(deduplicate_picks(all_picks))
    stations = {p["station"] for p in cluster}
    assert len(stations) >= 3
    assert {"IV.ATVO", "IV.ATMI", "IV.ATFO"}.issubset(stations)
