"""Download the pinned Umbertide replay with GEOFON's EIDA routing service.

Run with python scripts/download_replay.py. The output goes to data/raw/.
Waveforms: INGV Rete Sismica Nazionale, DOI 10.13127/SD/X0FXNH7QFY.
Event reference: EMSC-RTS catalogue, event 20230309_0000266.

The archive can include samples outside the requested interval. Trim to
START_TIME and END_TIME (UTC) when preparing the replay windows.
"""

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROUTING_URL = "https://geofon.gfz.de/eidaws/routing/1/query"
STATIONS = ("ATVO", "ATMI", "ATFO", "ATPC", "MURB", "APEC")
START_TIME = "2023-03-09T19:07:06"
END_TIME = "2023-03-09T19:10:06"
OUTPUT = Path(__file__).resolve().parents[1] / "data/raw/umbertide_20230309.mseed"


def main():
    query = urlencode(
        {
            "service": "dataselect",
            "format": "post",
            "network": "IV",
            "station": ",".join(STATIONS),
            "location": "--",
            "channel": "HH?",
            "starttime": START_TIME,
            "endtime": END_TIME,
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

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(waveforms)
    print(f"Saved {len(waveforms):,} bytes to {OUTPUT}")


if __name__ == "__main__":
    main()
