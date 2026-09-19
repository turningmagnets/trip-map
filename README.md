# Trip Map — Poker Rooms + MTB Trails

Single-page travel planner combining Austen’s **poker rooms** and **MTB trails** maps: shared Esri dark basemap, tabbed markers/filters, and an expanded **route planner** with intermediate stops and alternate OSRM drives.

**Generated:** 2026-09-18 (America/Los_Angeles)  
**For:** Austen Silva — SecondBrain travel tooling

## Open

```bash
open "/Users/austen/Library/CloudStorage/GoogleDrive-austen.silva@gmail.com/My Drive/SecondBrain/outputs/trip-map/index.html"
```

Works via `file://` (data in `data/rooms.js` + `data/trails.js`). Needs network for Leaflet CDN, Esri tiles, Nominatim geocoding, and OSRM routing.

Box copy: `/workspace/trip-map/`

## Tabs

| Tab | Markers / legend | Filters (no state filter) |
|-----|------------------|---------------------------|
| **Poker** | Size bands ≤5 / 6–10 / 11–20 / 21+ | Size band, games (NLH default / all / limit-spread), search, unknown tables, unknown games |
| **Trails** | Rating colors: rose 4.0–4.3 · lime 4.4–4.7 · cyan 4.8+ (no numbers on map) | Sources, min votes, difficulty blue/blueBlack/black only, min stars, last-5y toggle, search |

Switching tabs swaps markers, filters, legend, and side list. Shared basemap + trip planner stay put.

## Trip / route planner (side panel)

1. **Start** and **End** city inputs (Nominatim, ~1.1s polite delay between calls)
2. **Stops** — add intermediate places; order is start → stops… → end
3. **Find routes** → public OSRM driving with `alternatives=3`, full GeoJSON overview
4. **Alternate routes** listed with duration (“5h 20m”), distance (mi), and count of **active-tab** markers within ~50 mi of that polyline (plus a short top list)
5. Selecting a route draws it, corridor-filters markers, and `fitBounds` to the path
6. Clear route / clear stops
7. **Alt+click** map: set start, then end (stops still via input)

Corridor counts respect the **current tab’s filters**.

## Dataset snapshot

| Dataset | Loaded |
|---------|--------|
| Poker rooms (`data/rooms.js`) | **434** (318 with table counts) |
| MTB trails (`data/trails.js`) | **10,256** (mtbproject 6969 · trailforks 3287; blue→black, ★≥4, no double-black) |

## Basemap

Esri World Dark Gray Base + Reference (avoids OSM tile-server 403).

## OSRM notes

- Demo endpoint: `https://router.project-osrm.org/` — fair-use / rate-limited; not for production volume.
- `alternatives=3` typically returns the primary route plus up to ~2 alternates (server-dependent; more waypoints can reduce or eliminate alts).
- Multi-stop routes include all waypoints in order; alternate geometries still share those via-points.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Full app |
| `data/rooms.js` | Poker dataset |
| `data/trails.js` | Trails dataset |
| `SOURCES.md` | Provenance |
| `README.md` | This file |
