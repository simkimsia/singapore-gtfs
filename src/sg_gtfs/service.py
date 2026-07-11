"""Feed-wide service model: one weekday service over a fixed daytime span.

These are feed-level modeling decisions rather than properties of any one
mode (docs/ASSUMPTIONS.md §1–2), so both the rail and bus builders read them
from here.
"""

SERVICE_ID = "WD"
SPAN_START_S = 5 * 3600 + 30 * 60  # 05:30:00
SPAN_END_S = 23 * 3600 + 30 * 60  # 23:30:00


def hhmmss(seconds: int) -> str:
    return f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
