# Sources — Trip Map (combined)

**Build date:** 2026-09-18 (PT / America/Los_Angeles)  
**Purpose:** Personal travel planning for Austen Silva (SecondBrain). Combined UI only — datasets are copies of the existing poker and trails maps (not re-scraped for this release).

## Poker rooms

Copied from `/workspace/poker-rooms-map/data/rooms.js` (same generation as the poker-rooms-map app).

Primary upstream (see that project’s `SOURCES.md`):

- **DeucesCracked** state directories — table counts
- **PokerLog** — coordinates / discovery
- Geocoding: PokerLog geo, US Cities centroids, Nominatim

**Count in this copy:** 434 rooms (318 with tables).

## MTB trails

**Count:** 22,980 trails (mtbproject 10,436 · trailforks 3,286 · openstreetmap 9,236 · county/park 22).

The 2026-09-18 file had **10,256** trails. It was a copy of an older map that kept only ★≥4 blue / blue-black / black trails from two partial sources. That dropped 1,132 archived trails rated 4.5★ or higher (mostly easy and easy/intermediate, plus double-black) and it had no Silver Lake County Park trails at all: the MTB Project archive (`US_trails_half_step.csv`, 26,754 rows) does not contain that Kenosha County system.

### Where each source comes from

- **MTB Project archive** — `sgreylewis/mtb-trail-finder` `data/US_trails_half_step.csv`, the same public archive the previous file used. Included now: every trail rated **4.5★+** (any difficulty, including easy and double-black), other trails rated **4.0★+**, and trails rated **3.5★+** with at least 10 votes. Connectors are included only at 4.0★+. Unrated (0-star) archive rows are not included.
- **MTB Project trail pages** — public trail pages for Silver Lake County Park (Salem Lakes), fetched with the site’s crawl delay. Ratings and vote counts are copied only from those pages and linked back. Used to rate the county GIS geometries. `0` with no votes is stored as unrated, not as a zero-star score.
- **Trailforks** — the 3,287 records already in this map (one duplicate point removed). **Not re-crawled.** Trailforks’ data use policy allows their data only through an API key and says not to copy it for non-personal use, so this public map does not pull a new Trailforks dump.
- **OpenStreetMap** — named `route=mtb` relations in the continental US, Canada, Alaska, and Hawaii, plus named ways tagged `mtb:scale` (grouped so segments of one trail are one marker). © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright). These do not include star ratings.
- **Kenosha County GIS** — public feature service `KenoshaCounty_AllTrails_view` (purpose-built mountain bike trails at Silver Lake Park and Petrifying Springs Park). Difficulty and length come from the county. Coordinates are the trail line’s centroid. Star ratings are attached only when the MTB Project page above matched the trail by name.

Rebuild with `python3 scripts/build_trails.py` (uses cached downloads under `/tmp` when present).

### Coverage check (same bounding boxes)

| Area | Before | After | of which 4.5★+ |
|---|---:|---:|---:|
| Silver Lake County Park, Salem Lakes, WI | 0 | 15 | 6 |
| Moab, UT | 66 | 149 | 29 |
| Bentonville, AR | 102 | 289 | 33 |
| Kingdom Trails, VT | 37 | 52 | 26 |
| Copper Harbor, MI | 21 | 78 | 13 |
| Pisgah / Brevard, NC | 70 | 86 | 30 |

Silver Lake trails now on the map include Snowflake (4.8★, 6 votes), The Pines (4.8★), Silver Lake Techy Side (4.7★, 18 votes), Tike-onderoga (5.0★), Creekside Connector (5.0★), and Out & Back Connector (5.0★), plus the rest of the county’s named trails at that park (K-D Line, Rudie's Run, Little Wing, Yeti, Barbed Wire, Old Gravel Pit, and the hike/ski/bike connectors).

The map’s default filters are min rating 4.0 and min votes 5. Trails rated 4.5★ or higher stay visible even with fewer votes, and unrated OpenStreetMap / county trails stay visible. High Line (3.9★) is in the file and shows if min rating is set to 3.5.

## Runtime services (browser)

| Service | Use |
|---------|-----|
| Esri ArcGIS Online Canvas World Dark Gray | Basemap tiles |
| Nominatim (OSM) | City/place geocoding (≤1 req/s, USA bias) |
| OSRM public demo router | Driving routes + alternatives |
| unpkg Leaflet 1.9.4 | Map UI |

## Not invented

No fabricated rooms, trails, ratings, or table counts. Corridor “hits” are geometric distance to the OSRM polyline only.
