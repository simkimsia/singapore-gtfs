"""Collects the LTA train map station fragments.

Saves the raw station index and every per-station HTML fragment (first/last
train, frequencies, peak periods) under data/raw/lta-map/. See docs/SOURCES.md.
"""

import re
import time
from pathlib import Path

import requests

BASE = "https://www.lta.gov.sg/map/"
OUT = Path(__file__).parents[2] / "data" / "raw" / "lta-map"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) singapore-gtfs data extraction"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(UA)

    index = session.get(BASE + "mrt/index.xml", timeout=30)
    index.raise_for_status()
    (OUT / "index.xml").write_bytes(index.content)

    files = sorted(set(re.findall(r"<file>(mrt/[^<]+\.html)</file>", index.text)))
    print(f"{len(files)} station fragments")

    missing = []
    for i, rel in enumerate(files, 1):
        dest = OUT / rel.removeprefix("mrt/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            continue
        resp = session.get(BASE + rel, timeout=30)
        if resp.status_code == 404:
            # Index sometimes lists stations whose pages don't exist yet
            # (unopened lines/extensions). Record and move on.
            missing.append(rel)
            continue
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"[{i}/{len(files)}] {rel}")
        time.sleep(0.15)

    if missing:
        (OUT / "MISSING.txt").write_text("\n".join(missing) + "\n")
        print(f"{len(missing)} fragments 404'd (see MISSING.txt): {missing}")


if __name__ == "__main__":
    main()
