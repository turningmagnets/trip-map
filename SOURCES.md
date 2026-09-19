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

Copied from `/workspace/mtb-trails-map/data/trails.js`.

Primary upstream (see that project’s `SOURCES.md`):

- **MTB Project** archive via sgreylewis/mtb-trail-finder CSV
- **Trailforks** public HTML geo + detail crawl (no API keys)
- Filters baked into dataset: ★≥4; blue / blueBlack / black; **no double-black / proline**

**Count in this copy:** 10,256 trails (mtbproject 6969 · trailforks 3287).

## Runtime services (browser)

| Service | Use |
|---------|-----|
| Esri ArcGIS Online Canvas World Dark Gray | Basemap tiles |
| Nominatim (OSM) | City/place geocoding (≤1 req/s, USA bias) |
| OSRM public demo router | Driving routes + alternatives |
| unpkg Leaflet 1.9.4 | Map UI |

## Not invented

No fabricated rooms, trails, ratings, or table counts. Corridor “hits” are geometric distance to the OSRM polyline only.
