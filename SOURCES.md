# Sources — Trip Map (combined)

**Build date:** 2026-10-02 (UTC)  
**Purpose:** Personal travel planning for Austen Silva (SecondBrain).

## Poker rooms

Copied from `/workspace/poker-rooms-map/data/rooms.js` (same generation as the poker-rooms-map app).

Primary upstream (see that project’s `SOURCES.md`):

- **DeucesCracked** state directories — table counts
- **PokerLog** — coordinates / discovery
- Geocoding: PokerLog geo, US Cities centroids, Nominatim

**Count in this copy:** 434 rooms (318 with tables).

## MTB trails

**Count:** 10,261 trails (mtbproject 6,974 · trailforks 3,287). The 2026-09-18 map had **10,256**.

The map only lists **blue, blue/black, and black** trails rated **4.0 or higher**. Easy, easy/intermediate, and double-black stay off, including when another source gives them a high star rating. Default filters are min rating 4.0 and min votes 10, same as the 2026-09-18 map.

### What was dropping qualifying trails

Qualifying means blue / blue-black / black and ★≥4.0 on MTB Project or Trailforks. Counts below are measured against the MTB Project archive (`sgreylewis/mtb-trail-finder` `data/US_trails_half_step.csv`, 26,754 rows, last committed **2018-01-23**) plus the Silver Lake County Park pages fetched from MTB Project.

| Cause | Before | After |
|---|---:|---:|
| Connector rows (type `Connector`; 122 of 131 have 1 vote and an empty summary). Still excluded, matching the original filter. | 131 | 131 |
| Same trail already on the map as Trailforks (normalized name, coordinates rounded to 0.001°). Kept as one marker. | 208 | 208 |
| Archive row with no Trailforks match and not on the map (Rim Trail, Cañon City CO; Whiskey Creek, Minturn CO) | 2 | 0 |
| Stale archive: Silver Lake blue–black ★≥4 pages whose ids are newer than the 2018 file | 3 | 0 |

The archive has **7,310** blue–black ★≥4 rows. **6,969** of those were already the MTB Project half of the 2026-09-18 map. 6,969 + 131 + 208 + 2 = 7,310.

Those 208 Trailforks matches sit a median of about 35 feet from the archive point. They are not missing. Trailforks rows in this file use only blue and black (no blue/black band): of the 208, 73 are blue/black on MTB Project and blue or black on Trailforks. Both bands are allowed, so the trail still shows.

Not causes of the gap, checked and ruled out: a region cap, a per-state quota, a vote cutoff (included trails go down to 1 vote), and a same-name dedupe inside MTB Project (only 2 of the 210 non-connector omissions share a name with a nearby included MTB row).

### Silver Lake County Park, Salem Lakes, WI

The 2018 archive has no trails in this park. Public MTB Project pages (crawl delay respected) rate the named trails as follows. Only the blue–black ★≥4 rows are on the map:

| Trail | Stars | Votes | MTB Project difficulty | On the map |
|---|---:|---:|---|---|
| Silver Lake Techy Side | 4.7 | 18 | blue/black | yes |
| KD Line | 4.4 | 9 | blue | yes |
| Little Wing | 4.2 | 9 | blue | yes |
| Snowflake | 4.8 | 6 | easy/intermediate | no |
| The Pines | 4.8 | 5 | easy/intermediate | no |
| Tike-onderoga | 5.0 | 2 | easy | no |
| Out & Back Connector | 5.0 | 2 | easy/intermediate | no |
| Creekside Trail | 5.0 | 1 | easy | no |
| Rudie's Run | 4.4 | 7 | easy/intermediate | no |
| Yeti | 4.3 | 7 | easy | no |
| Barbed Wire | 4.0 | 6 | easy/intermediate | no |
| High Line | 3.9 | 8 | blue/black | no (below 4.0) |
| Hike/Ski/Bike Trail | 3.0 | 1 | easy/intermediate | no |
| Hike/Ski/Bike Trail East | unrated | 0 | easy | no |

Kenosha County GIS calls Rudie's Run and Barbed Wire “More Difficult,” which is not the same scale as MTB Project blue. Those two stay off because MTB Project rates them easy/intermediate. County labels are not used for difficulty. County length is copied only when the name matches a trail already included from MTB Project (KD Line 0.52 mi, Little Wing 1.32 mi). Techy Side is not in the county layer under that name, so it has no length.

With the default min-votes filter of 10, Techy Side (18 votes) is visible and KD Line and Little Wing (9 votes each) are in the file but hidden until Min votes is lowered. That vote floor is the original control, not a dataset drop.

### Sources

- **MTB Project archive** — the same CSV as the 2026-09-18 file. Inclusion: difficulty blue / blueBlack / black, ★≥4.0, type other than Connector, and not already represented by a Trailforks point at the rounded coordinate.
- **MTB Project trail pages** — the three Silver Lake trails above. Ratings, votes, difficulty, summary, and coordinates come from those pages.
- **Trailforks** — the 3,287 records already on the 2026-09-18 map. **Not re-crawled.** Trailforks’ data policy allows their data only through an API key and says not to copy it for non-personal use, so trails that exist only on Trailforks and were missed by that earlier crawl are still absent.
- **Not used for trails:** OpenStreetMap `route=mtb` and `mtb:scale` ways have no star rating, so they fail the 4.0 floor. Unrated county trails (including Petrifying Springs) are not included.

The archive also contains 12,003 rows that are not blue–black (easy, easy/intermediate, double-black, or missing difficulty) and 7,441 blue–black rows under 4.0 stars. Those stay out on purpose.

Rebuild with `python3 scripts/build_trails.py`. It reads `main:data/trails.js` as the baseline, the CSV at `/tmp/US_trails_half_step.csv`, and `/tmp/trail-build/ratings.jsonl`.

### Coverage check (same bounding boxes)

| Area | Before | After | of which 4.5★+ |
|---|---:|---:|---:|
| Silver Lake County Park, Salem Lakes, WI | 0 | 3 | 1 |
| Salem Lakes area | 0 | 3 | 1 |
| Moab, UT | 66 | 66 | 25 |
| Bentonville, AR | 102 | 102 | 26 |
| Kingdom Trails, VT | 37 | 37 | 23 |
| Copper Harbor, MI | 21 | 21 | 9 |
| Pisgah / Brevard, NC | 70 | 70 | 28 |

Moab, Bentonville, Kingdom Trails, Copper Harbor, and Pisgah do not gain markers: the blue–black ★≥4 archive rows that were absent there already have a Trailforks point on the map. The new archive rows (Rim Trail, Whiskey Creek) are outside those boxes.

## Runtime services (browser)

| Service | Use |
|---------|-----|
| Esri ArcGIS Online Canvas World Dark Gray | Basemap tiles |
| Nominatim (OSM) | City/place geocoding (≤1 req/s, USA bias) |
| OSRM public demo router | Driving routes + alternatives |
| unpkg Leaflet 1.9.4 | Map UI |

## Not invented

No fabricated rooms, trails, ratings, or table counts. Corridor “hits” are geometric distance to the OSRM polyline only.
