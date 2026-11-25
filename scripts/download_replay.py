"""Download a pinned replay with GEOFON's EIDA routing service.

Run with python scripts/download_replay.py for Umbertide, or add tyrol
for the Austrian replay. The output goes to data/raw/.

Umbertide waveforms: INGV Rete Sismica Nazionale, DOI 10.13127/SD/X0FXNH7QFY.
Tyrol waveforms: GeoSphere Austria, Austrian Seismic Network, DOI 10.7914/SN/OE.
Event references: data/replay/emsc_reference.csv, from the EMSC-RTS catalogue.

The archive can include samples outside the requested interval. Trim to
the selected clip's start and end times (UTC) when preparing replay windows.
"""

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROUTING_URL = "https://geofon.gfz.de/eidaws/routing/1/query"
CLIPS = {
    "umbertide": {
        "network": "IV",
        "stations": ("ATVO", "ATMI", "ATFO", "ATPC", "MURB", "APEC"),
        "start_time": "2023-03-09T19:07:06",
        "end_time": "2023-03-09T19:10:06",
        "filename": "umbertide_20230309.mseed",
    },
    "tyrol": {
        "network": "OE",
        "stations": ("SQTA", "MOTA", "WATA", "WTTA", "FETA", "RETA", "DAVA", "ABTA", "LESA"),
        "start_time": "2024-10-31T19:18:42",
        "end_time": "2024-10-31T19:21:42",
        "filename": "tyrol_20241031.mseed",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Download a QuakeShift replay.")
    parser.add_argument("clip", choices=CLIPS, nargs="?", default="umbertide")
    clip = CLIPS[parser.parse_args().clip]

    query = urlencode(
        {
            "service": "dataselect",
            "format": "post",
            "network": clip["network"],
            "station": ",".join(clip["stations"]),
            "location": "--",
            "channel": "HH?",
            "starttime": clip["start_time"],
            "endtime": clip["end_time"],
        }
    )
    with urlopen(f"{ROUTING_URL}?{query}", timeout=30) as response:
        route = response.read().decode("ascii").strip()

    endpoint, _, selection = route.partition("\n")
    if not selection or "\n\n" in selection:
        raise SystemExit("Expected one EIDA archive for the pinned stations.")

    request = Request(
        endpoint,
        data=(selection + "\n").encode("ascii"),
        headers={"Content-Type": "text/plain"},
    )
    with urlopen(request, timeout=60) as response:
        waveforms = response.read()
        if not waveforms or response.headers.get_content_type() != "application/vnd.fdsn.mseed":
            raise SystemExit("The EIDA archive did not return MiniSEED waveforms.")

    output = Path(__file__).resolve().parents[1] / "data/raw" / clip["filename"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(waveforms)
    print(f"Saved {len(waveforms):,} bytes to {output}")


if __name__ == "__main__":
    main()
