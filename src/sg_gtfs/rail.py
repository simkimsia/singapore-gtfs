"""Assemble the rail half of the feed: stops, routes, trips, times, transfers.

Stations become a parent stop plus one child stop per line code; trains serve
the child, and transfers.txt (the vendored measured walks, no buffer) joins
children at interchanges. Trips are frequency-based: one template trip per
pattern and direction over the fixed 05:30-23:30 span (docs/SOURCES.md).
"""

from sg_gtfs import concordance, headways, rail_times, topology
from sg_gtfs.service import SERVICE_ID, SPAN_END_S, SPAN_START_S, hhmmss


def stops() -> list[dict]:
    rows = []
    for station in concordance.stations():
        multi = len(station.codes) > 1
        if multi:  # single-code stations need no parent (id would collide)
            rows.append(
                {
                    "stop_id": station.parent_id,
                    "stop_name": station.name,
                    "stop_lat": station.lat,
                    "stop_lon": station.lon,
                    "location_type": 1,
                    "parent_station": "",
                }
            )
        for code in station.codes:
            rows.append(
                {
                    "stop_id": code,
                    "stop_name": station.name,
                    "stop_lat": station.lat,
                    "stop_lon": station.lon,
                    "location_type": 0,
                    "parent_station": station.parent_id if multi else "",
                }
            )
    return rows


def routes() -> list[dict]:
    return [
        {
            "route_id": p.route_id,
            "agency_id": "LTA",
            "route_short_name": p.route_id,
            "route_long_name": p.route_name,
            "route_type": p.route_type,
        }
        for p in topology.patterns()
    ]


def _directed_stopcodes(pattern: topology.Pattern) -> list[tuple[str, list[str]]]:
    """(direction suffix, ordered stop codes).

    Circular patterns traverse the loop twice in one trip: with single-lap
    frequency trips, any journey crossing the lap seam would need a phantom
    same-stop transfer (up to a headway of extra wait). Two laps let every
    possible loop journey happen inside one trip.
    """
    forward = list(pattern.codes)
    if pattern.circular:
        forward = forward + forward + [forward[0]]
    backward = forward[::-1]
    return [("0", forward), ("1", backward)]


def trips_and_times() -> tuple[list[dict], list[dict], list[dict]]:
    trips, stop_times, frequencies = [], [], []
    for pattern in topology.patterns():
        hop_seconds = [round(m * 60) for m in rail_times.hop_minutes(pattern)]
        if pattern.circular:
            hop_seconds = hop_seconds * 2  # two laps (see _directed_stopcodes)
        headway_s = round(headways.headway_minutes()[pattern.route_id] * 60)
        for direction, codes in _directed_stopcodes(pattern):
            trip_id = f"{pattern.route_id}_{direction}"
            trips.append(
                {
                    "route_id": pattern.route_id,
                    "service_id": SERVICE_ID,
                    "trip_id": trip_id,
                    "direction_id": direction,
                }
            )
            hops = hop_seconds if direction == "0" else hop_seconds[::-1]
            t = SPAN_START_S
            for seq, code in enumerate(codes, 1):
                stop_times.append(
                    {
                        "trip_id": trip_id,
                        "arrival_time": hhmmss(t),
                        "departure_time": hhmmss(t),
                        "stop_id": code,
                        "stop_sequence": seq,
                    }
                )
                if seq <= len(hops):
                    t += hops[seq - 1]
            frequencies.append(
                {
                    "trip_id": trip_id,
                    "start_time": hhmmss(SPAN_START_S),
                    "end_time": hhmmss(SPAN_END_S),
                    "headway_secs": headway_s,
                }
            )
    return trips, stop_times, frequencies


def transfers() -> list[dict]:
    from sg_gtfs import raw

    rows = []
    for row in raw.read_csv_rows(raw.TRANSFER_TIMING):
        rows.append(
            {
                "from_stop_id": row["Start Code"],
                "to_stop_id": row["End Code"],
                "transfer_type": 2,  # requires the given minimum time
                "min_transfer_time": round(float(row["Transfer time in seconds"])),
            }
        )
    return rows
