# Sources — Trip Map (combined)

**Build date:** 2026-10-08 (MT) — trails rebuilt; poker unchanged since 2026-10-02  
**Purpose:** Personal travel planning for Austen Silva (SecondBrain).

## Poker rooms

Copied from `/workspace/poker-rooms-map/data/rooms.js` (same generation as the poker-rooms-map app).

Primary upstream (see that project’s `SOURCES.md`):

- **DeucesCracked** state directories — table counts
- **PokerLog** — coordinates / discovery
- Geocoding: PokerLog geo, US Cities centroids, Nominatim

**Count in this copy:** 434 rooms (318 with tables).

## MTB trails

**Rebuilt 2026-10-08 (MT).** Cutoff lowered from ★4.0 to **★3.8**, plus a completeness pass over the whole local Trailforks crawl cache.

**Count:** **12,563** trails (trailforks 6,082 · mtbproject 6,481), incl. 147 Trailforks trails from the 2026-10 browser pass (trailhead point only). Previous file (2026-10-02): 10,261.

| | Count |
|---|---:|
| ★ 3.8–3.99 | 1,779 |
| ★ 4.0–4.49 | 7,661 |
| ★ 4.5–4.99 | 1,849 |
| ★ 5.0 | 1,274 |
| blue / blue-black / black | 7,058 / 1,917 / 3,588 |
| Default view (★≥3.8, ≥10 votes) | 5,094 (was 3,006 at ★≥4.0) |

Only **blue, blue/black, and black** trails are listed; easy, easy/intermediate, double-black, and proline stay off. The ride-recording export (`data/trails_export.json` / `.csv`) has every trail in the file regardless of the map's vote filter, with Trailforks GPS track lines for 5,872 of them. `data/trails_export_other_difficulty.*` holds ★≥3.8 trails dropped only by the difficulty rules (not shown on the map).

### What changed vs the 2026-10-02 file

| Change | Trails |
|---|---:|
| New ★3.8–3.99 trails (Trailforks 1,217 · MTB Project 305) | +1,522 |
| Trailforks ★≥4.0 trails already in the Sep 2026 crawl cache but missing from the old build (built before enrichment finished; old parser sometimes read another trail's rating widget) | +1,432 |
| MTB Project markers folded into the same Trailforks trail (name match, ≤1 km; MTB Project id kept in `alt_ids`) | −780 |
| Removed non-US entry (Flow, Iwakuni, Japan) | −1 |
| **Net** | **+2,173** |

### Rating basis

- **Trailforks:** the rating shown on the trail page (Trailforks' Bayesian rating, e.g. "3.86 / 5 with 11 votes"; shown with two decimals in popups). Low-vote trails sit near Trailforks' ~3.98 prior. If only a directory card exists, its raw average is used.
- **MTB Project:** archive star average (`sgreylewis/mtb-trail-finder` CSV, last committed 2018-01-23) plus public trail pages for the Silver Lake trails below.

### Silver Lake County Park, Salem Lakes, WI

The 2018 archive has no trails in this park. Public MTB Project pages (crawl delay respected) rate the named trails as follows. Only the blue–black ★≥3.8 rows are on the map (originally ★≥4.0; High Line joined at 3.8):

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
| High Line | 3.9 | 8 | blue/black | yes (since the 3.8 cutoff, 2026-10-08) |
| Hike/Ski/Bike Trail | 3.0 | 1 | easy/intermediate | no |
| Hike/Ski/Bike Trail East | unrated | 0 | easy | no |

Kenosha County GIS calls Rudie's Run and Barbed Wire “More Difficult,” which is not the same scale as MTB Project blue. Those two stay off because MTB Project rates them easy/intermediate. County labels are not used for difficulty. County length is copied only when the name matches a trail already included from MTB Project (KD Line 0.52 mi, Little Wing 1.32 mi). Techy Side is not in the county layer under that name, so it has no length.

With the default min-votes filter of 10, Techy Side (18 votes) is visible and KD Line and Little Wing (9 votes each) are in the file but hidden until Min votes is lowered. That vote floor is the original control, not a dataset drop.

### Sources

- **MTB Project archive** — `US_trails_half_step.csv` (26,754 rows). Inclusion: blue / blueBlack / black, ★≥3.8, type other than Connector.
- **MTB Project trail pages** — Silver Lake Techy Side, KD Line, Little Wing (2026-10-02), High Line (2026-10-08).
- **Trailforks** — cached public HTML from the Sep 2026 crawl (7,426 detail pages, 2,132 directory cards, 152,724 region-table rows). **Not re-crawled:** trailforks.com blocks this machine (Cloudflare 403) since Oct 7, 2026. Trailforks' data policy allows bulk data only via an API key.
- **Not used for the rated layer:** OpenStreetMap (no star ratings). It is used only as an unrated geometry cross-check in the mtb-trails-map project.

### Known gaps

- **Idaho Trailforks region was never crawled** (its slug is `idaho-3166`). Idaho Trailforks trails on the map come only from directory cards (55 of them). Estimated ~0.9–1.1k rated blue/black Idaho Trailforks trails are missing. Boise, Pocatello and Sun Valley coverage relies mostly on the 2018 MTB Project archive.
- **~37.8k Trailforks blue/black trails with 1–9 votes** appear in the cached region tables but have no cached rating or coordinates. Because of the Bayesian prior, an estimated ~28–33k of them would display ★≥3.8. Closing this needs a browser pass over their detail pages or a Trailforks API key.
- ~36k blue/black Trailforks trails have 0 votes (unrated) and can never meet a star cutoff.

Rebuild: `/workspace/mtb-trails-map/scripts/parse_cache_v2.py` then `build_trails_dataset.py` (copies in `scripts/`). The older `scripts/build_trails.py` (2026-10-02, ★4.0) is superseded.

## Runtime services (browser)

| Service | Use |
|---------|-----|
| Esri ArcGIS Online Canvas World Dark Gray | Basemap tiles |
| Nominatim (OSM) | City/place geocoding (≤1 req/s, USA bias) |
| OSRM public demo router | Driving routes + alternatives |
| unpkg Leaflet 1.9.4 | Map UI |

## Not invented

No fabricated rooms, trails, ratings, or table counts. Corridor “hits” are geometric distance to the OSRM polyline only.
