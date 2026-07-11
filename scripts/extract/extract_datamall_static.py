"""Collects LTA DataMall static geospatial datasets (no API key).

Bus stop coordinates also come from the BusStops API during the bus build;
the shapefile here is a keyless fallback/cross-check.
"""

from pathlib import Path

import requests

BASE = "https://datamall.lta.gov.sg/content/dam/datamall/datasets/Geospatial/"
FILES = [
    "TrainStation_Mar2026.zip",
    "TrainStationExit.zip",
    "Train Station Codes and Chinese Names.zip",
    "BusStopLocation_Mar2026.zip",
]
OUT = Path(__file__).parents[2] / "data" / "raw" / "datamall-static"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) singapore-gtfs data extraction"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = OUT / name.replace(" ", "_")
        resp = requests.get(BASE + name, headers=UA, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"{dest.name}: {len(resp.content):,} bytes")


if __name__ == "__main__":
    main()
