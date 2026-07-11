# Data sources

Every field in the feed traces back to an official source or to a model
documented in [ASSUMPTIONS.md](ASSUMPTIONS.md). Hand-curated data is used
only where it is vendored into this repo and attributed. All sources were
verified live on 2026-07-06 unless noted. The extracts in `data/raw/` are
dated snapshots, and the builder (`src/sg_gtfs/`) works only from them — it
never touches the network.

Each source below follows the same rubric: **what it is · how we obtained it ·
what we took from it · attribution & terms · verification performed**.

## Why this feed exists

The community-maintained Singapore GTFS feed we evaluated first was
structurally unusable for routing. Interchange stations existed in
`stops.txt` but appeared in zero `stop_times.txt` rows — no train ever
stopped at Jurong East, Dhoby Ghaut, City Hall, Raffles Place, or Bishan — so
rail-to-rail transfers were impossible. All three LRT systems had routes but
no trips. There was no `transfers.txt` at all. And the schedules were
synthetic: a flat 3 minutes between every station pair, with flat headways of
about 6 minutes. Any isochrone computed from that feed systematically
understates reach around MRT hubs.

**Decision (2026-07-06):** build a feed directly from primary data — LTA, the
operators, and government sources — with no intermediate GitHub projects in the
chain.

## 1. LTA DataMall — bus network + rail geometry

**What it is.** The Land Transport Authority's open data portal
(https://datamall.lta.gov.sg), offering realtime/static APIs (free API key) and
keyless static downloads.

**How we obtained it.**
- `BusStops`, `BusRoutes`, `BusServices` APIs, paged 500 records per call —
  `scripts/extract/extract_datamall_bus.py`, run 2026-07-06 (needs
  `DATAMALL_ACCOUNT_KEY`, see `.env.example`). API User Guide v6.8 (Apr 2026).
- Static geospatial datasets (no key) — `scripts/extract/extract_datamall_static.py`:
  *Train Station* shapefile (Mar 2026), *Train Station Exit Point* shapefile
  (Jul 2026), *Train Station Codes and Chinese Names* XLS, *Bus Stop Location*
  shapefile.

**What we took.**
- `BusStops.csv` (5,205 stops): stop code, name, lat/lon → bus `stops.txt`.
- `BusRoutes.csv` (26,799 rows): per-service stop sequence with cumulative
  distance and per-stop first/last bus times → bus `stop_times.txt` run times
  (first-bus differencing, see ASSUMPTIONS.md §bus).
- `BusServices.csv` (796 services): four time-band frequency ranges → bus
  `frequencies.txt` headways.
- Train Station shapefile: polygon centroids → rail stop coordinates.
- Train Station Exit shapefile: exit-point centroids for stations newer than the
  polygon file (CCL6, Punggol Coast).
- (The Station Codes XLS and Bus Stop Location shapefile are archived in
  `data/raw/datamall-static/` but not consumed by the current builder.)

**Attribution & terms.** Singapore Open Data Licence v1.0 — see
[NOTICE.md](../NOTICE.md).

**Verification performed.** Referential integrity on the dump: every stop
referenced by `BusRoutes` exists in `BusStops`; every service in `BusRoutes`
exists in `BusServices`. Coordinates spot-checked against the published network
map; centroid fallback covered by `tests/test_concordance.py`.

## 2. LTA train map fragments — headways and service structure

**What it is.** The interactive train map at
`lta.gov.sg/content/ltagov/en/map/train.html` is a JS shell over static
per-station HTML fragments.

**How we obtained it.** `scripts/extract/extract_lta_map.py`, run 2026-07-06:
index at `https://www.lta.gov.sg/map/mrt/index.xml` (183 stations; interchanges
use combined codes like `EW24-NS1`), then
`https://www.lta.gov.sg/map/mrt/{LINE}/{CODE}.html` per station. One station
(DT36) is indexed but 404s — an unopened Downtown Line extension, recorded in
`data/raw/lta-map/MISSING.txt`.

**What we took.** The Mon–Fri "Train Service Frequencies" rows: peak and
off-peak headway ranges per station and direction → averaged per-route headways
in `frequencies.txt` (`src/sg_gtfs/headways.py`). The fragments also carry
per-direction first/last-train times and peak-period definitions; those are
archived but not used (see ASSUMPTIONS.md §service-span).

**Attribution & terms.** LTA website content; Singapore Open Data Licence
attribution applied as for DataMall — see NOTICE.md.

**Verification performed.** Every route must obtain a headway or the build
fails; `tests/test_rail_data.py` bounds all headways to a plausible 2–25 min and
checks known relationships (e.g. the Bukit Panjang ring headway exceeds the stem's).

## 3. SimplyGo travel guide — official station-to-station travel times

**What it is.** SimplyGo (TransitLink) operates a public fare-and-travel-time
lookup at `https://travelguide.simplygo.com.sg/MRT`, returning an "Estimated
Travel Time" in whole minutes for any pair of the 184 open MRT/LRT stations.

**How we obtained it.** `scripts/extract/extract_simplygo.py`, run 2026-07-06
with targeted additions 2026-07-07, rate-limited and retried; every raw response
is archived in `data/raw/simplygo/raw_html.tar.gz` so the extraction is
re-parseable without re-querying. The station list (`stations.csv`) doubles as
our canonical station registry.

**What we took.** 1,691 station-pair times (`travel_times.csv`): all ~460
adjacent pairs in both directions, per-line terminus profiles, direct 2–4-hop
windows for NS/CC/DT, all pairs within the LRT petals and the Changi branch,
plus 150 random cross-line pairs held out purely for validation. These drive the
MRT inter-station run times in `stop_times.txt` via the calibration model in
`src/sg_gtfs/rail_times.py` (summarised in ASSUMPTIONS.md §rail-run-times), and
the Bukit Panjang LRT fallback rate.

**Attribution & terms.** Factual travel-time estimates from a public service
operated by SimplyGo Pte Ltd — see NOTICE.md. This repo stores derived numbers
and archived responses; it is not affiliated with SimplyGo.

**Verification performed.** `scripts/extract/check_simplygo.py` gates the
extraction: hop values within range, adjacent pairs direction-symmetric within
1 minute, profiles monotonic. Spot checks against lived journeys (e.g.
Hougang→Kovan 2 min, Bukit Panjang→Fajar 4 min, Admiralty→Aljunied 42 min).
`tests/test_rail_data.py` asserts the calibrated line totals still match the
SimplyGo terminal-to-terminal figures. The 150 held-out pairs
(`kind == "validation-sample"`, excluded from all fitting) were routed once
through a multimodal router loaded with this feed before it was adopted
downstream: median +4 min vs SimplyGo (p10 +0, p90 +7) — the offset is the
initial wait and street access that a door-to-door router charges and
SimplyGo's platform-to-platform estimate doesn't.

## 4. SBS Transit travel-time charts — Sengkang/Punggol LRT hop times

**What it is.** SBS Transit publishes adjacent-station travel-time charts as
image assets on `https://www.sbstransit.com.sg/travel-time` (SELRT/SWLRT/
PELRT/PWLRT.jpg).

**How we obtained it.** Manually transcribed 2026-07-07 into
`data/raw/sbs-transit/lrt_travel_times.csv`, one row per adjacent hop, source
image URL retained per row. There is no scraper — the source is an image.

**What we took.** Exact adjacent hop minutes for the four SBS-operated LRT
loops, e.g. Sengkang East `STC→SE1→SE2→SE3→SE4→SE5→STC = 2,1,1,1,2,3` min. Used
directly for routes SKE/SKW/PGE/PGW; reverse-direction trips use the reversed
sequence. Bukit Panjang LRT is not SBS-operated and stays on the SimplyGo-derived
fallback.

**Attribution & terms.** Published operator data, © SBS Transit — see NOTICE.md.

**Verification performed.** `tests/test_rail_data.py` asserts the built hop
sequences reproduce the published charts exactly, in both directions.

## 5. Interchange transfer times — vendored community measurements

**What it is.** A public Google Sheet of measured interchange walk times
(https://docs.google.com/spreadsheets/d/1e-Tuf6rHBFsgsuFN7XqbFL8ec_vdRjQw):
a "Timing" sheet with 72 directional rows (e.g. Jurong East NS↔EW
cross-platform 10 s; Woodlands NSL→TEL 260 s) and an "Extra remarks" sheet with
platform-level nuance. Measured field data by transit enthusiasts on reddit! [Reddit Post](https://www.reddit.com/r/singapore/comments/10wkygf/mrt_map_with_transfer_timing/)

**How we obtained it.** `scripts/extract/extract_transfers.py`, run 2026-07-06
(`/export?format=xlsx`). The original workbook is preserved as
`data/raw/transfers/transfer_times.xlsx`; remarks as `remarks.txt`.

**What we took.** All directional transfer walk times, normalized at extraction
so the builder sees only current station codes: CE1/CE2 → CC34/CC33 (Circle Line
loop-closure renumbering) and the two Tanah Merah CG rows dropped (the Changi
branch shares stop EW4 in this feed, making that transfer implicit) → 70 rows in
`timing.csv`, emitted as `transfers.txt` with `transfer_type=2` and
`min_transfer_time` set to the measured seconds.

**Attribution & terms.** Community-measured data, vendored with attribution —
see NOTICE.md. Consistent with the primary-data rule only because it is vendored
row-by-row in this repo and treated as our curated table.

**Verification performed.** Every remaining code verified against the current
network (`checks.py` fails the build on unknown stops); every multi-line
interchange must be crossable via at least one transfer row (fatal gate);
`tests/test_build.py` pins the row count and asserts full directed-pair coverage
at Marina Bay and Bayfront. **Decision (2026-07-06):** the measured walks are
used as-is with no added buffer.
