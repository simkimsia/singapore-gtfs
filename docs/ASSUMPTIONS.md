# Assumptions and modeling decisions

There's several things missing for us to be able to directly create a GTFS feed.
Firstly, there is no published Singapore bus timetable. There is no official document
anywhere that says bus 174 leaves this stop at 09:41. What DOES exists is
a patchwork of indirect sources: frequency ranges like "every 8–12 minutes",
first- and last-bus times for every stop, station-to-station journey times
from the SimplyGo trip planner, and community-measured walking times inside
interchanges.

So, in fact, this feed is not *really* a timetable. It's a **model of a typical
Singapore weekday**, stitched together from those sources, based on how *often*
things run and how *long* they take, rather than on any particular 09:41 departure. 
Wherever primary data didn't exist, or precision wouldn't have changed the answer, 
we modeled. 

In this process, many judgement calls were made. Each one of those is written down here: 
what we decided, and why.

## The calendar: one weekday, repeated

**Every day in the feed is the same Monday-to-Friday day.** A single service
(`WD`) runs Mon–Fri from 2026 through 2030. There is no weekends, no public
holidays, no `calendar_dates.txt`. Sundays and public holidays already share
a schedule in reality, and the whole point of the feed is a typical weekday,
so that's all we built. *(`service.py::SERVICE_ID`, `build.py::CALENDAR` —
decided 2026-07-06)*

**Everything runs 05:30–23:30.** Real first and last trains vary by line and
station, but once frequencies are averaged (next point), exact first/last
times stop mattering for a daytime journey. The archived LTA fragments keep
the real spans if we ever want them back. We did try deriving rail run times
from first-train timings and dropped it. This is because first trains launch from several
points along a line at once, so the arithmetic doesn't work.
*(`service.py::SPAN_START_S/SPAN_END_S` — revised 2026-07-07)*

**One template trip per route per direction, plus a frequency.** Instead of
generating thousands of individual scheduled trips, each route gets one
representative trip and a note saying "this repeats every N minutes"
(GTFS's `frequencies.txt`). Since we're just modeling a
typical day, we really don't gain much from enumerating every trip.
*(`rail.py::trips_and_times`, `bus.py::trips_and_times`)*

**Peak and off-peak are averaged.** LTA publishes waiting
times as separate peak and off-peak ranges ("2–3 min peak, 5–7 min
off-peak"). We take the midpoint of every published weekday range across a
line's station pages and average them into a single number per route. A
daytime isochrone doesn't repay the extra precision of time-varying
headways. *(`headways.py` — decided 2026-07-06)*

**Buses with no published frequency get 15 minutes.** A handful of services
have all four of their frequency bands unpublished; they're assigned a
15-minute headway. *(`bus.py::DEFAULT_HEADWAY_MIN`)*

## How long trains take (`rail_times.py`)

While there's no official run-time table, we *do* have SimplyGo, the
public journey planner, which reports whole-minute travel times between any
two stations.

**Adjacent station pairs from SimplyGo are the baseline.** We take the time
between every neighbouring pair, keyed to the *physical* station — so a hop
measured on one line also serves the same physical hop on another.

**Calibration only ever adds time, never removes it.** We noticed that summing lots of
whole-minute hops systematically underestimates a full journey (by comparing the sum with the data from the SimplyGo).
We suspect this is because everything is rounded to the nearest minute and every station dwell is not accounted for.
So we correct upward against longer SimplyGo journeys, in two ways:

- On the **EW, NE and TE lines**, end-to-end times seem accurate 
  (because the fastest way between two stations appear to sitting on the line all the way), so
  adjacent hops are stretched until their sums match SimplyGo's
  terminus-to-terminus profiles. This ensures that any adjustment is strictly an overestimate.
- On the **NS, CC, CG and DT lines**, long SimplyGo journeys can't be
  trusted. The planner might route via a faster parallel line.
  Here, we use short 2–4-hop SimplyGo windows to understand the dwells/rounding instead.

**Floors and caps for rounding artifacts.** Whole-minute reporting means
very short hops come back as "0 minutes" (Little India→Rochor, really).
Hops are floored at 0.75 min, and MRT hops capped at 8 min.
*(`MIN_HOP_MINUTES`, `MAX_MRT_HOP_MINUTES`)*

**The LRTs are special-cases.** For the Sengkang and Punggol loops, SBS
actually publishes adjacent-station timing charts. Bukit
Panjang has neither charts nor clean adjacent data, so it gets one fitted
pace for the whole line: the median minutes-per-hop from multi-hop SimplyGo
pairs, clamped to 0.75–2.0 min/hop. *(revised 2026-07-07)*

**Circular lines go around the loop twice per trip.** If a loop trip
covered the circle exactly once, a journey crossing the trip's start/end
seam would look like it needs a transfer onto its own train. Writing the
loop twice into one trip (CC loop, BP ring, LRT petals) lets any loop
journey fit in a single trip. *(`rail.py::_directed_stopcodes`)*

## How long buses take (`bus.py`)

**The day's first bus is a measured schedule in disguise.** LTA publishes,
for every stop, when the first bus of the day passes it (`WD_FirstBus`).
That first departure is one physical vehicle driving the whole route — so
subtracting consecutive stops' first-bus times gives the time the bus
actually took between them. 95.9% of bus hops in the current dump come from
this differencing, clean.

**Where differencing breaks, a speed curve fills in.** Short-working trips
and missing times leave gaps. For those we fitted a fallback from the ~24k
cleanly measured hops: median speed by hop distance — about 15 km/h for
hops under 1 km, about 31 km/h beyond 3 km. Conveniently, this means long
expressway hops inherit expressway pace without us ever having to classify
which services are express. *(`bus.py::_fallback_curve`)*

**Bus times are inflated by 5%.** First buses run before dawn, in no
traffic. `BUS_RUNTIME_MULTIPLIER = 1.05` is a conservative daytime-traffic
adjustment applied to bus in-vehicle time only — never to rail, walking,
transfers, or waiting. *(top of `bus.py`)*

**No bus hop is shorter than 30 seconds.** *(`bus.py::MIN_HOP_S`)*

## Stations and transfers

**SimplyGo decides which stations exist.** Its station list (184) is the
canonical set of open stations — it correctly excludes the closed Ten Mile
Junction and the unopened DT36. Coordinates come from DataMall's station
polygon centroids, falling back to the centroid of a station's exits for
stations newer than the polygon shapefile (CCL6, Punggol Coast).
*(`concordance.py`)*

**An interchange is one parent station with a child stop per line.**
Transfers connect the children; a parent is emitted only when a station
actually carries multiple line codes. *(`rail.py::stops`)*

**Measured transfer walks are used as-is, no safety buffer.** Community
measurements of interchange walking times go straight in (`transfer_type=2`,
`min_transfer_time` = the measured seconds) — they're taken to be high
quality. Interchange pairs nobody has measured aren't fatal: routers will
street-route between the co-located child stops. *(decided 2026-07-06)*

## Left out on purpose

- **No `shapes.txt`** — route geometry is cosmetic; it doesn't change any
  routing result. (DataMall has rail geometry if it's ever wanted.)
- **No `pathways.txt` or `levels.txt`** — `transfers.txt` already carries
  the interchange cost.
- **No Saturday/Sunday service and no `calendar_dates.txt`** — see the
  calendar section above.
