# Data collection scripts

This is the collection layer: the scripts that populate `data/raw/` from
primary sources (each source is documented in
[docs/SOURCES.md](../../docs/SOURCES.md)). They were last run 2026-07-06 and
are rerunnable, but today a refresh is a manual, supervised job — sources
shift, and fresh data deserves a review before it is committed. Making
refresh a routine operation is the project's direction; see
[CONTRIBUTING.md](../../CONTRIBUTING.md).

Run any script with `uv run --group extract python scripts/extract/<name>.py`.
One source has no script at all: the SBS Transit LRT timings are published as
images, so they are transcribed by hand into
`data/raw/sbs-transit/lrt_travel_times.csv`.

| Script | Fetches | Notes |
|---|---|---|
| `extract_lta_map.py` | LTA train map station fragments | Skips already-downloaded files; 404s recorded in `MISSING.txt` |
| `extract_simplygo.py` | SimplyGo station-pair travel times | ~1,700 rows: per-line terminus profiles, all adjacent pairs both ways, direct 2-4 hop windows for NS/CC/DT, all pairs in LRT petals/branches, 150 random cross-line validation pairs |
| `extract_transfers.py` | Interchange transfer-time Google Sheet | Normalizes codes to the current network (CE→CC renames, CG rows dropped) — xlsx keeps the original |
| `extract_datamall_static.py` | DataMall geospatial zips | Keyless static downloads |
| `extract_datamall_bus.py` | DataMall bus APIs (BusStops/BusRoutes/BusServices) | Needs `DATAMALL_ACCOUNT_KEY` in `.env`; pages 500 records per call |
| `check_simplygo.py` | — (validation only) | Sanity gates on the extracted travel times: hop ranges, direction symmetry, profile monotonicity (info-level; see docstring) |
