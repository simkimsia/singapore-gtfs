# Contributing

This project needs two kinds of help, and only one of them involves writing
code.

## If you know the network

The most valuable thing you can offer is local knowledge. If you ride the
network and something in this feed doesn't match reality — a run time, a
frequency, a transfer, a stop — [open an issue](../../issues/new/choose).
Tell me what the feed says, what's actually true, and how you know.

Before you do, skim [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md). This feed
models a typical weekday, so some gaps (no weekend calendars, averaged
headways) are deliberate decisions rather than bugs. But every assumption in
that file is an open invitation: if you can point to a better number, a
better method, or a source I haven't seen, I want to hear about it.

## Where this is heading

Today, the data in `data/raw/` is a set of snapshots I collected by hand —
scraping SimplyGo, pulling DataMall, transcribing operator charts — and the
automated part is the build that turns them into a valid GTFS. That works
today, but it won't stay accurate on its own. Bus routes change. New stations
open.

The goal is for this repo to become the feed Singapore can rely on.
Concretely:

- separate the **collection** layer (online, refreshes `data/raw/`) from the
  **build** layer (offline, deterministic) — today the split is only informal
- make collection rerunnable, starting with the bus network via DataMall,
  which is where real-world change actually happens
- eventually, refresh and release on a schedule, so the published feed tracks
  the real network

If that sounds like something you'd enjoy building, check the open issues or
open one describing what you'd like to take on.

## Working on the code

Setup is in the [README](README.md#quickstart). A PR has to pass
`uv run ruff check .` and `uv run pytest -q`; CI also runs the MobilityData
gtfs-validator on the built zip and requires zero errors (warnings are
reviewed and accepted — see the [Validation section of the
README](README.md#validation)).
For anything non-trivial, open an issue first so we agree on the approach
before you spend an evening on it.

If your change touches the data or the model, say in the PR description what
changed in the feed output and why, and update the matching entry in
[docs/SOURCES.md](docs/SOURCES.md) or
[docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md). The ideal data-fix PR is the fix,
the doc update, and a source for the corrected value. If that's more than you
signed up for, an issue with the evidence is genuinely enough. I'll take it
from there.
