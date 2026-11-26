"""PhaseNet picker for balanced mode, matching the CONTRACTS.md picks format.

Run `python -m pickers.phasenet` (or pass `tyrol`) to test against a local replay.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np
from obspy import Stream, Trace, UTCDateTime

MODEL_VERSION = "phasenet-instance-v2"


def format_utc_ms(value: Any) -> str:
    """Format a UTC timestamp as ISO-8601 milliseconds with trailing Z."""
    return (UTCDateTime(value) + 0.0005).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_stream(window: dict[str, Any]) -> Stream:
    """Convert one CONTRACTS.md waveform window into a 3-channel ObsPy Stream."""
    network, station = window["station"].split(".", 1)
    start = UTCDateTime(window["window_start"])
    rate = float(window["sample_rate_hz"])

    traces = [
        Trace(
            data=np.asarray(window["channels"][axis], dtype=np.float64),
            header={
                "network": network,
                "station": station,
                "location": "",
                "channel": f"HH{axis}",
                "sampling_rate": rate,
                "starttime": start,
            },
        )
        for axis in "ZNE"
    ]
    if len({len(tr.data) for tr in traces}) != 1 or len(traces[0].data) == 0:
        raise ValueError(f"Window {window['window_id']} needs non-empty equal-length Z/N/E channels")
    return Stream(traces)


class PhaseNetPicker:
    """Runs SeisBench PhaseNet (INSTANCE v2) on 60-second windows and returns CONTRACTS.md picks."""

    def __init__(self, profile: str = "balanced", source: str = "live", model: Any = None) -> None:
        self.profile = profile
        self.source = source
        if model is None:
            import seisbench.models as sbm

            model = sbm.PhaseNet.from_pretrained("instance", version_str="2")
            model.to("cpu")
            model.eval()
        self.model = model

    def pick_window(
        self,
        window: dict[str, Any],
        *,
        source: str | None = None,
        picked_at: str | None = None,
    ) -> list[dict[str, Any]]:
        """Identify P and S arrivals in one waveform window in CONTRACTS.md `picks` format."""
        output = self.model.classify(build_stream(window))
        picked_iso = format_utc_ms(picked_at or UTCDateTime())
        ingested_iso = window.get("ingested_at") or picked_iso
        start = UTCDateTime(window["window_start"])
        end = UTCDateTime(window["window_end"])
        station = window["station"]

        picks = []
        for raw in output.picks:
            phase = str(raw.phase).upper()
            peak = UTCDateTime(raw.peak_time)
            if phase not in ("P", "S") or not (start <= peak < end):
                continue
            pick_time = format_utc_ms(peak)
            picks.append(
                {
                    "pick_id": f"{station}:{phase}:{pick_time}:{self.profile}",
                    "window_id": window["window_id"],
                    "station": station,
                    "phase": phase,
                    "pick_time": pick_time,
                    "probability": round(float(raw.peak_value), 4),
                    "profile": self.profile,
                    "model_version": MODEL_VERSION,
                    "source": source or self.source,
                    "ingested_at": ingested_iso,
                    "picked_at": picked_iso,
                }
            )
        return sorted(picks, key=lambda p: (p["pick_time"], p["phase"]))


def deduplicate_picks(picks: list[dict[str, Any]], tolerance_s: float = 0.5) -> list[dict[str, Any]]:
    """Merge repeated (station, phase) picks within +-tolerance_s, keeping highest probability."""
    merged: list[dict[str, Any]] = []
    for pick in sorted(picks, key=lambda p: (p["station"], p["phase"], p["pick_time"])):
        if (
            merged
            and merged[-1]["station"] == pick["station"]
            and merged[-1]["phase"] == pick["phase"]
            and abs(UTCDateTime(pick["pick_time"]) - UTCDateTime(merged[-1]["pick_time"])) <= tolerance_s
        ):
            if pick["probability"] > merged[-1]["probability"]:
                merged[-1] = pick
        else:
            merged.append(pick)
    return sorted(merged, key=lambda p: (p["pick_time"], p["station"], p["phase"]))


def find_p_cluster(picks: list[dict[str, Any]], window_s: float = 10.0) -> list[dict[str, Any]]:
    """Return the largest set of distinct-station P picks arriving within `window_s`."""
    p_picks = sorted((p for p in picks if p["phase"] == "P"), key=lambda p: p["pick_time"])
    best: list[dict[str, Any]] = []
    for i, first in enumerate(p_picks):
        t0 = UTCDateTime(first["pick_time"])
        by_station: dict[str, dict[str, Any]] = {}
        for p in p_picks[i:]:
            if UTCDateTime(p["pick_time"]) - t0 > window_s:
                break
            sta = p["station"]
            if sta not in by_station or p["probability"] > by_station[sta]["probability"]:
                by_station[sta] = p
        if len(by_station) > len(best):
            best = sorted(by_station.values(), key=lambda p: p["pick_time"])
    return best if len(best) >= 3 else []


def main() -> None:
    from ingestor.replay import replay_windows
    from scripts.download_replay import CLIPS

    parser = argparse.ArgumentParser(description="Run balanced PhaseNet on a local replay.")
    parser.add_argument("clip", choices=CLIPS, nargs="?", default="umbertide")
    clip = parser.parse_args().clip

    picker = PhaseNetPicker(profile="balanced")
    all_picks = [p for w in replay_windows(clip) for p in picker.pick_window(w)]
    unique = deduplicate_picks(all_picks)
    cluster = find_p_cluster(unique)

    print(f"{clip}: {len(all_picks)} raw picks, {len(unique)} unique (+-0.5s)")
    for p in unique:
        print(f"  {p['station']:8s} {p['phase']} {p['pick_time']}  p={p['probability']:.4f}")

    if not cluster:
        raise SystemExit("FAIL: fewer than 3 stations picked P within 10 seconds")

    span = UTCDateTime(cluster[-1]["pick_time"]) - UTCDateTime(cluster[0]["pick_time"])
    print(f"\nPASS: {len(cluster)} stations picked P within {span:.2f}s: {', '.join(p['station'] for p in cluster)}")
    print("\nSample CONTRACTS.md pick:\n" + json.dumps(cluster[0], indent=2))


if __name__ == "__main__":
    main()
