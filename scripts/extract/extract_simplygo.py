"""Collects SimplyGo station-to-station travel times.

Strategy (see docs/SOURCES.md): per line, scrape cumulative profiles from both
termini plus all adjacent pairs (both directions); NS/CC/DT also get direct 2-4
hop sliding windows so local calibration does not rely on shortcut-prone
terminus profiles; small lines/LRT petals get all ordered pairs; plus a random
cross-line validation sample. Times come back in whole minutes, so hop times
are later estimated from the combined measurements rather than any single
differenced pair.

Outputs under data/raw/simplygo/:
  stations.csv      — SimplyGo numeric id, display name, station codes
  travel_times.csv  — from_id, to_id, from_codes, to_codes, kind, minutes
  raw_html.tar.gz   — every response, for re-parsing without re-scraping
"""

import csv
import random
import re
import tarfile
import time
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import requests

BASE = "https://travelguide.simplygo.com.sg"
OUT = Path(__file__).parents[2] / "data" / "raw" / "simplygo"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) singapore-gtfs data extraction"}
DELAY = 0.25
CROSS_LINE_SAMPLES = 150

CODE_RE = re.compile(r"^([A-Z]{2})(\d+)$")
# LRT hub codes attach to their petal lines rather than forming a line of their own.
HUBS = {"STC": ["SE", "SW"], "PTC": ["PE", "PW"]}
# Branch junctions: parent-line station that the branch physically departs from.
JUNCTIONS = {"CG": "EW4", "CE": "CC4"}
# Small groups where we just take every ordered pair.
ALL_PAIRS_LINES = {"SE", "SW", "PE", "PW", "CG", "CE", "BP"}
# Closed loops: also join last numeric code back to first.
LOOPS = {"BP": ("BP13", "BP6")}
WINDOW_HOPS = (2, 3, 4)
WINDOW_LINES = {"NS", "CC", "DT"}


def parse_stations(html: str):
    # Scope to the boarding-station select only: the page's other dropdowns
    # (e.g. "Search By") reuse small numeric values, and mixing them in once
    # silently overwrote station id 1 (Yio Chu Kang) with a junk entry.
    select = re.search(
        r'<select id="BoardingStation".*?</select>', html, re.DOTALL
    ).group(0)
    opts = set(re.findall(r'<option value="(\d+)">([^<]+)</option>', select))
    stations = {}
    for sid, name in opts:
        name = name.strip()
        m = re.search(r"\[([^\]]+)\]$", name)
        codes = m.group(1).split("/") if m else []
        stations[sid] = {"name": name, "codes": codes}
    return stations


def build_lines(stations):
    """line prefix -> [(numeric code, station id)] sorted by code."""
    lines = defaultdict(list)
    for sid, st in stations.items():
        for code in st["codes"]:
            m = CODE_RE.match(code)
            if m:
                lines[m.group(1)].append((int(m.group(2)), sid))
            elif code in HUBS:
                for petal in HUBS[code]:
                    lines[petal].append((0, sid))  # hub sorts before SE1 etc.
    return {k: sorted(set(v)) for k, v in lines.items()}


def code_to_station(stations):
    return {c: sid for sid, st in stations.items() for c in st["codes"]}


def plan_pairs(stations):
    lines = build_lines(stations)
    by_code = code_to_station(stations)
    pairs = defaultdict(list)  # (from, to) -> [kind, ...], fetched once

    def add(a, b, kind):
        if a != b and kind not in pairs[(a, b)]:
            pairs[(a, b)].append(kind)

    for line, members in lines.items():
        seq = [sid for _, sid in members]
        if line in JUNCTIONS and by_code.get(JUNCTIONS[line]):
            seq = [by_code[JUNCTIONS[line]]] + seq
        if len(seq) < 2:
            continue
        if line in ALL_PAIRS_LINES:
            for a in seq:
                for b in seq:
                    add(a, b, f"{line}-allpair")
            continue
        for terminus in (seq[0], seq[-1]):
            for s in seq:
                add(terminus, s, f"{line}-profile")
        for a, b in zip(seq, seq[1:]):
            add(a, b, f"{line}-adjacent")
            add(b, a, f"{line}-adjacent")

    for line, (a, b) in LOOPS.items():
        if by_code.get(a) and by_code.get(b):
            add(by_code[a], by_code[b], f"{line}-adjacent")
            add(by_code[b], by_code[a], f"{line}-adjacent")

    for line in sorted(WINDOW_LINES):
        if line not in lines:
            continue
        seq = [sid for _, sid in lines[line]]
        if line == "CC":
            seq = [sid for n, sid in lines[line] if n >= 4]  # CC4..CC34 loop, no CC1 branch
        for i in range(len(seq)):
            for gap in WINDOW_HOPS:
                if line == "CC":
                    forward = [seq[(i + k) % len(seq)] for k in range(gap + 1)]
                    backward = [seq[(i - k) % len(seq)] for k in range(gap + 1)]
                    add(forward[0], forward[-1], f"{line}-window")
                    add(backward[0], backward[-1], f"{line}-window")
                elif i + gap < len(seq):
                    window = seq[i : i + gap + 1]
                    add(window[0], window[-1], f"{line}-window")
                    add(window[-1], window[0], f"{line}-window")

    rng = random.Random(42)
    ids = sorted(stations)
    added = 0
    while added < CROSS_LINE_SAMPLES:
        a, b = rng.sample(ids, 2)
        if (a, b) not in pairs:
            add(a, b, "validation-sample")
            added += 1
    return pairs


def fetch_pair(session, a, b):
    for attempt in range(3):
        try:
            r = session.post(
                f"{BASE}/MRT/PartialFareSearch",
                data={"BoardingStation": a, "AlightingStation": b},
                timeout=30,
            )
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == 2:
                raise
            print(f"  retry {a}->{b}: {e}")
            time.sleep(2 * (attempt + 1))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(UA)

    page = session.get(f"{BASE}/MRT", timeout=30)
    page.raise_for_status()
    stations = parse_stations(page.text)
    print(f"{len(stations)} stations")

    with open(OUT / "stations.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["simplygo_id", "name", "codes"])
        for sid in sorted(stations, key=int):
            st = stations[sid]
            w.writerow([sid, st["name"], "/".join(st["codes"])])

    pairs = plan_pairs(stations)
    print(f"{len(pairs)} pair queries planned")

    mins_re = re.compile(r"(\d+)\s*mins")
    results, failures = [], []
    with tarfile.open(OUT / "raw_html.tar.gz", "w:gz") as tar:
        for n, ((a, b), kinds) in enumerate(sorted(pairs.items()), 1):
            html = fetch_pair(session, a, b)
            blob = html.encode()
            info = tarfile.TarInfo(f"{a}-{b}.html")
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))

            m = mins_re.search(html)
            if m:
                for kind in kinds:
                    results.append((a, b, kind, int(m.group(1))))
            else:
                for kind in kinds:
                    failures.append((a, b, kind))
            if n % 100 == 0:
                print(f"[{n}/{len(pairs)}] ok={len(results)} fail={len(failures)}")
            time.sleep(DELAY)

    with open(OUT / "travel_times.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_id", "to_id", "from_codes", "to_codes", "kind", "minutes"])
        for a, b, kind, mins in results:
            w.writerow(
                [a, b, "/".join(stations[a]["codes"]), "/".join(stations[b]["codes"]), kind, mins]
            )

    print(f"done: {len(results)} times, {len(failures)} failures")
    for a, b, kind in failures:
        print(f"  NO TIME: {a}->{b} ({kind})")


if __name__ == "__main__":
    main()
