# Raw data snapshots

Everything the feed builder reads lives here: dated snapshots of every
primary source, pulled 2026-07-06 by the scripts in `scripts/extract/`
(targeted SimplyGo window rows and the SBS Transit LRT chart timings were
added 2026-07-07). The builder works only from these files and never touches
the network, so anyone can reproduce the feed without API keys or scraping.

These are snapshots, not living data. Refreshing them is currently a manual
job, and making it routine is the project's direction — see
[CONTRIBUTING.md](../../CONTRIBUTING.md). Full source documentation and
method decisions are in [docs/SOURCES.md](../../docs/SOURCES.md).

| Folder | Source | Contents |
|---|---|---|
| `lta-map/` | lta.gov.sg train map fragments | `index.xml` + 182 per-station HTML files: per-direction first/last train, peak & off-peak headways, peak periods. `MISSING.txt`: DT36 listed in index but unopened (404) |
| `simplygo/` | travelguide.simplygo.com.sg fare/time lookup | `stations.csv` (numeric ID ↔ name ↔ station codes), `travel_times.csv` (1,691 station-pair times, whole minutes, including NS/CC/DT 2-4 hop windows), `raw_html.tar.gz` (every response, re-parseable offline) |
| `sbs-transit/` | SBS Transit travel-time charts | `lrt_travel_times.csv` manually transcribes the published adjacent timings from the SELRT/SWLRT/PELRT/PWLRT image charts, with source URLs retained per row |
| `transfers/` | Public Google Sheet of measured interchange walk times (see docs/SOURCES.md for link) | `transfer_times.xlsx` (original), `timing.csv` (70 directional rows, **normalized**: CE1/CE2→CC34/CC33, Tanah Merah CG-platform rows dropped), `remarks.txt` (34 platform-level notes) |
| `datamall-static/` | LTA DataMall static datasets (keyless) | Train station, station exit, station codes/Chinese names, bus stop location shapefiles |
| `datamall-bus/` | LTA DataMall APIs (key in `.env`), dumped 2026-07-06 | `BusStops.csv` (5,205), `BusRoutes.csv` (26,799 rows with cumulative `Distance` per stop), `BusServices.csv` (796, with per-band frequency ranges). Referential integrity verified: all route stops exist in BusStops, all services present in both files |

Every input the builder needs is in this folder.
