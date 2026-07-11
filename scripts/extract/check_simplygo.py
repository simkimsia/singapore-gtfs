"""Sanity checks for the extracted SimplyGo travel times (see docs/SOURCES.md §3).

These replace first-train differencing as validation of rail run times:
 1. adjacent-pair hop times must be 0-8 min (long gaps like Expo->Changi are 7);
 2. A->B vs B->A adjacent times must agree within 1 min;
 3. terminus profiles are checked for monotonicity, but decreases are reported
    as info only: SimplyGo routes far pairs via faster parallel lines, and CC
    is a closed loop, so profiles are cross-checks on monotonic segments, not
    a derivation source. Adjacent pairs are the primary hop source.

Prints violations; exits non-zero if any hard check fails.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parents[2] / "data" / "raw" / "simplygo"
CODE_RE = re.compile(r"^([A-Z]{2})(\d+)$")
LRT = {"BP", "SE", "SW", "PE", "PW"}


def line_position(codes, line):
    for code in codes.split("/"):
        m = CODE_RE.match(code)
        if m and m.group(1) == line:
            return int(m.group(2))
    return None


def main():
    rows = list(csv.DictReader(open(DATA / "travel_times.csv")))
    print(f"{len(rows)} measurements")
    problems = []

    profiles = defaultdict(list)  # (line, terminus id) -> [(pos, minutes)]
    for r in rows:
        kind = r["kind"]
        line = kind.split("-")[0]
        if kind.endswith("-profile"):
            pos = line_position(r["to_codes"], line)
            if pos is not None:
                profiles[(line, r["from_id"])].append((pos, int(r["minutes"])))
        elif kind.endswith("-adjacent") or kind.endswith("-allpair"):
            a = line_position(r["from_codes"], line)
            b = line_position(r["to_codes"], line)
            if a is None or b is None or abs(a - b) != 1:
                continue
            mins = int(r["minutes"])
            lo, hi = (0, 3) if line in LRT else (0, 8)
            if not lo <= mins <= hi:
                problems.append(
                    f"hop range: {r['from_codes']}->{r['to_codes']} = {mins} min (expect {lo}-{hi})"
                )

    offline = []
    for (line, terminus), pts in sorted(profiles.items()):
        if line == "CC":  # closed loop: profiles wrap, expected non-monotonic
            continue
        pts.sort()
        direction = 1 if pts and pts[0][1] <= pts[-1][1] else -1
        ordered = pts[::direction]
        for (p1, m1), (p2, m2) in zip(ordered, ordered[1:]):
            if m2 < m1:
                offline.append(
                    f"{line} from {terminus}: pos {p1}={m1} min but pos {p2}={m2} min"
                )

    sym = {}
    for r in rows:
        if r["kind"].endswith("-adjacent"):
            sym[(r["from_id"], r["to_id"])] = int(r["minutes"])
    for (a, b), m in sym.items():
        rev = sym.get((b, a))
        if rev is not None and abs(m - rev) > 1:
            problems.append(f"asymmetric adjacent: {a}->{b}={m} but {b}->{a}={rev}")

    if offline:
        print(f"\n{len(offline)} profile segments routed off-line (info, excluded from derivation):")
        for p in offline:
            print(f"  {p}")

    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print(f"  {p}")
        sys.exit(1)
    print("\nall hard checks passed")


if __name__ == "__main__":
    main()
