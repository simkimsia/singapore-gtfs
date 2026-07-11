"""Collects the LTA DataMall bus APIs (BusStops, BusRoutes, BusServices).

Needs DATAMALL_ACCOUNT_KEY in .env (repo root) or the environment — see
.env.example. Pages through each endpoint (500 records per call) and writes
one CSV per dataset under data/raw/datamall-bus/, keeping every field the API
returns.
"""

import csv
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parents[2]
OUT = ROOT / "data" / "raw" / "datamall-bus"
BASE = "https://datamall2.mytransport.sg/ltaodataservice/"
DATASETS = ["BusStops", "BusRoutes", "BusServices"]
PAGE = 500


def account_key():
    if key := os.environ.get("DATAMALL_ACCOUNT_KEY"):
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DATAMALL_ACCOUNT_KEY" and value.strip():
                return value.strip()
    raise SystemExit("DATAMALL_ACCOUNT_KEY not set — see .env.example")


def fetch_all(session, dataset):
    records, skip = [], 0
    while True:
        r = session.get(f"{BASE}{dataset}", params={"$skip": skip}, timeout=60)
        r.raise_for_status()
        page = r.json()["value"]
        records.extend(page)
        if len(page) < PAGE:
            return records
        skip += PAGE
        time.sleep(0.1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"AccountKey": account_key(), "accept": "application/json"})

    for dataset in DATASETS:
        records = fetch_all(session, dataset)
        dest = OUT / f"{dataset}.csv"
        with open(dest, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            w.writeheader()
            w.writerows(records)
        print(f"{dataset}: {len(records)} records -> {dest.name}")


if __name__ == "__main__":
    main()
