"""Read a pinned replay and yield one waveform window per station."""

import argparse
from collections import Counter
from pathlib import Path

from obspy import UTCDateTime, read

from scripts.download_replay import CLIPS

SAMPLE_RATE_HZ = 100
WINDOW_SECONDS = 60
STEP_SECONDS = 10
RAW_DATA = Path(__file__).resolve().parents[1] / "data/raw"


def replay_windows(clip_name):
    """Yield waveform data in replay order. The sender adds timing metadata."""
    clip = CLIPS[clip_name]
    start = UTCDateTime(clip["start_time"])
    end = UTCDateTime(clip["end_time"])
    clip_seconds = int(end - start)
    stream = read(str(RAW_DATA / clip["filename"]), format="MSEED")

    station_samples = {}
    for code in clip["stations"]:
        station = f"{clip['network']}.{code}"
        traces = stream.select(network=clip["network"], station=code, location="")
        channels = {}
        for axis in "ZNE":
            channel = traces.select(channel=f"HH{axis}")
            if len(channel) != 1 or channel[0].stats.sampling_rate != SAMPLE_RATE_HZ:
                raise ValueError(f"{station} HH{axis} needs one continuous 100 Hz trace")
            # ObsPy includes the last sample. The replay end time is exclusive.
            samples = channel[0].slice(start, end - 1 / SAMPLE_RATE_HZ).data
            if len(samples) != clip_seconds * SAMPLE_RATE_HZ:
                raise ValueError(f"{station} HH{axis} does not cover the full clip")
            channels[axis] = samples
        station_samples[station] = channels

    for offset in range(0, clip_seconds - WINDOW_SECONDS + 1, STEP_SECONDS):
        first = offset * SAMPLE_RATE_HZ
        last = (offset + WINDOW_SECONDS) * SAMPLE_RATE_HZ
        window_start = (start + offset).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_end = (start + offset + WINDOW_SECONDS).strftime("%Y-%m-%dT%H:%M:%SZ")
        for station, channels in station_samples.items():
            yield {
                "window_id": f"{station}:{window_start}",
                "station": station,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "window_start": window_start,
                "window_end": window_end,
                "channels": {axis: samples[first:last].tolist() for axis, samples in channels.items()},
            }


def main():
    parser = argparse.ArgumentParser(description="Check the windows in a local replay.")
    parser.add_argument("clip", choices=CLIPS, nargs="?", default="umbertide")
    clip = parser.parse_args().clip
    counts = Counter(window["station"] for window in replay_windows(clip))
    print(f"{clip}: {sum(counts.values())} waveform windows across {len(counts)} stations")


if __name__ == "__main__":
    main()
