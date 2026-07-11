"""Paths and loaders for the committed primary-data extracts in data/raw/.

Every builder module reads raw inputs through here and only here. Nothing in
sg_gtfs/ touches the network (docs/SOURCES.md).
"""

import csv
from pathlib import Path

# src/sg_gtfs/raw.py -> parents[2] is the repo root
DATA_RAW = Path(__file__).parents[2] / "data" / "raw"

SIMPLYGO_STATIONS = DATA_RAW / "simplygo" / "stations.csv"
SIMPLYGO_TIMES = DATA_RAW / "simplygo" / "travel_times.csv"
SBS_LRT_TIMES = DATA_RAW / "sbs-transit" / "lrt_travel_times.csv"
TRANSFER_TIMING = DATA_RAW / "transfers" / "timing.csv"
LTA_MAP_DIR = DATA_RAW / "lta-map"
STATION_POLYGONS = DATA_RAW / "datamall-static" / "TrainStation_Mar2026.zip"
STATION_EXITS = DATA_RAW / "datamall-static" / "TrainStationExit.zip"
BUS_STOPS = DATA_RAW / "datamall-bus" / "BusStops.csv"
BUS_ROUTES = DATA_RAW / "datamall-bus" / "BusRoutes.csv"
BUS_SERVICES = DATA_RAW / "datamall-bus" / "BusServices.csv"


def read_csv_rows(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
