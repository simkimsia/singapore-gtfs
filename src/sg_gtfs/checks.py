"""Structural gates a generated feed must pass before the zip is written.

These encode the exact failures of the community feed we replaced
(docs/SOURCES.md): stops nothing serves, routes without trips, interchanges
you cannot transfer across. A failed gate aborts the build.
"""

from collections import defaultdict


def run(tables: dict[str, list[dict]]) -> list[str]:
    """Returns a list of failures; empty means the feed passes."""
    failures = []

    served = {st["stop_id"] for st in tables["stop_times"]}
    children = [s for s in tables["stops"] if s["parent_station"]]
    standalone = [s for s in tables["stops"] if not s["parent_station"] and s["location_type"] == 0]
    for stop in children + standalone:
        if stop["stop_id"] not in served:
            failures.append(f"stop {stop['stop_id']} ({stop['stop_name']}) is served by no trip")

    trips_per_route = defaultdict(int)
    for trip in tables["trips"]:
        trips_per_route[trip["route_id"]] += 1
    for route in tables["routes"]:
        if trips_per_route[route["route_id"]] == 0:
            failures.append(f"route {route['route_id']} has no trips")

    stop_ids = {s["stop_id"] for s in tables["stops"]}
    transfer_pairs = {(t["from_stop_id"], t["to_stop_id"]) for t in tables["transfers"]}
    for t in tables["transfers"]:
        for stop_id in (t["from_stop_id"], t["to_stop_id"]):
            if stop_id not in stop_ids:
                failures.append(f"transfer references unknown stop {stop_id}")

    by_parent = defaultdict(list)
    for stop in children:
        by_parent[stop["parent_station"]].append(stop["stop_id"])
    for parent, codes in by_parent.items():
        if len(codes) < 2:
            continue
        pairs = [(a, b) for a in codes for b in codes if a != b]
        if not any(p in transfer_pairs for p in pairs):
            failures.append(f"interchange {parent} has no transfer entries at all")

    return failures


def coverage_warnings(tables: dict[str, list[dict]]) -> list[str]:
    """Non-fatal: interchange child pairs without an explicit measured walk.

    Routers fall back to street-network walking between the (co-located)
    children, so a missing pair is survivable — but it should be a conscious gap.
    """
    transfer_pairs = {(t["from_stop_id"], t["to_stop_id"]) for t in tables["transfers"]}
    by_parent = defaultdict(list)
    for stop in tables["stops"]:
        if stop["parent_station"]:
            by_parent[stop["parent_station"]].append(stop["stop_id"])
    warnings = []
    for parent, codes in sorted(by_parent.items()):
        for a in codes:
            for b in codes:
                if a != b and (a, b) not in transfer_pairs:
                    warnings.append(f"no measured transfer {a} -> {b} at {parent}")
    return warnings
