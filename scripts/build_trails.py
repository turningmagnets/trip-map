#!/usr/bin/env python3
"""Rebuild data/trails.js inside the blue-to-black, 4.0+ constraint.

The map lists only blue, blue/black, and black trails rated 4.0 or higher.
This script starts from the 2026-09-18 dataset (git main) and adds qualifying
trails that pipeline was dropping:

- Archive rows (US_trails_half_step.csv) that are blue–black and ★≥4, are not
  connectors, and are not the same trail as a Trailforks point already on the
  map (normalized name + coordinates rounded to 0.001°).
- Public MTB Project pages in the ratings cache that meet the same rule and
  are missing from the 2018 archive. County difficulty labels are not used.

Trailforks is not re-crawled. OpenStreetMap geometries are not copied: they
have no star rating, so they fail the 4.0 floor.
"""

from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAILS_JS = ROOT / "data" / "trails.js"
CACHE = Path(os.environ.get("TRAIL_BUILD_CACHE", "/tmp/trail-build"))
CSV_PATH = Path(os.environ.get("MTB_CSV", "/tmp/US_trails_half_step.csv"))
CSV_URL = (
    "https://raw.githubusercontent.com/sgreylewis/mtb-trail-finder/"
    "master/data/US_trails_half_step.csv"
)
OSM_CONUS = Path(os.environ.get("OSM_CONUS", "/tmp/osm_routes_conus.json"))
OSM_NORTH = Path(os.environ.get("OSM_NORTH", "/tmp/osm_routes_north.json"))
RATINGS = CACHE / "ratings.jsonl"
KENOSHA_URL = (
    "https://services1.arcgis.com/G9PTZYkfeC1onwUV/arcgis/rest/services/"
    "KenoshaCounty_AllTrails_view/FeatureServer/0/query"
)
UA = "trip-map/1.0 (personal trip planner; trail coverage rebuild)"

DIFF_MAP = {
    "green": "green",
    "greenblue": "greenBlue",
    "blue": "blue",
    "blueblack": "blueBlack",
    "black": "black",
    "dblack": "doubleBlack",
    "doubleblack": "doubleBlack",
    "white": "green",
}
IMBA = {"0": "green", "1": "green", "2": "blue", "3": "black", "4": "doubleBlack"}
STS = {
    "0": "green",
    "1": "greenBlue",
    "2": "blue",
    "3": "blueBlack",
    "4": "black",
    "5": "doubleBlack",
    "6": "doubleBlack",
}
COUNTY_DIFF = {
    "easier trails": "green",
    "more difficult trails": "blue",
    "most difficult trails": "black",
    "double black diamond": "doubleBlack",
}

# Rough boxes, smallest match wins. Good enough to label OSM markers.
STATE_BOXES = [
    ("district of columbia", -77.12, 38.79, -76.91, 38.995),
    ("rhode island", -71.91, 41.15, -71.12, 42.02),
    ("delaware", -75.79, 38.45, -75.05, 39.84),
    ("connecticut", -73.73, 40.98, -71.79, 42.05),
    ("new jersey", -75.56, 38.93, -73.89, 41.36),
    ("massachusetts", -73.51, 41.24, -69.93, 42.89),
    ("new hampshire", -72.56, 42.70, -70.70, 45.31),
    ("vermont", -73.44, 42.73, -71.46, 45.02),
    ("maryland", -79.49, 37.91, -75.05, 39.72),
    ("hawaii", -160.25, 18.91, -154.81, 22.24),
    ("west virginia", -82.64, 37.20, -77.72, 40.64),
    ("south carolina", -83.35, 32.05, -78.54, 35.22),
    ("indiana", -88.10, 37.77, -84.78, 41.76),
    ("kentucky", -89.57, 36.50, -81.96, 39.15),
    ("tennessee", -90.31, 34.98, -81.65, 36.68),
    ("virginia", -83.68, 36.54, -75.24, 39.47),
    ("north carolina", -84.32, 33.84, -75.46, 36.59),
    ("pennsylvania", -80.52, 39.72, -74.69, 42.27),
    ("new york", -79.76, 40.50, -71.86, 45.02),
    ("ohio", -84.82, 38.40, -80.52, 41.98),
    ("georgia", -85.61, 30.36, -80.84, 35.00),
    ("alabama", -88.47, 30.22, -84.89, 35.01),
    ("mississippi", -91.66, 30.17, -88.10, 34.99),
    ("louisiana", -94.04, 28.93, -88.82, 33.02),
    ("arkansas", -94.62, 33.00, -89.64, 36.50),
    ("missouri", -95.77, 35.99, -89.10, 40.61),
    ("iowa", -96.64, 40.38, -90.14, 43.50),
    ("illinois", -91.51, 36.97, -87.50, 42.51),
    ("wisconsin", -92.89, 42.49, -86.75, 47.08),
    ("michigan", -90.42, 41.70, -82.41, 48.26),
    ("florida", -87.63, 24.52, -80.03, 31.00),
    ("maine", -71.08, 43.06, -66.95, 47.46),
    ("minnesota", -97.24, 43.50, -89.49, 49.38),
    ("oklahoma", -103.00, 33.62, -94.43, 37.00),
    ("kansas", -102.05, 36.99, -94.59, 40.00),
    ("nebraska", -104.05, 40.00, -95.31, 43.00),
    ("south dakota", -104.06, 42.48, -96.44, 45.95),
    ("north dakota", -104.05, 45.94, -96.55, 49.00),
    ("wyoming", -111.06, 40.99, -104.05, 45.01),
    ("colorado", -109.06, 36.99, -102.04, 41.00),
    ("new mexico", -109.05, 31.33, -103.00, 37.00),
    ("utah", -114.05, 36.99, -109.04, 42.00),
    ("arizona", -114.82, 31.33, -109.05, 37.00),
    ("idaho", -117.24, 41.99, -111.04, 49.00),
    ("montana", -116.05, 44.36, -104.04, 49.00),
    ("washington", -124.77, 45.54, -116.92, 49.00),
    ("oregon", -124.57, 41.99, -116.46, 46.29),
    ("nevada", -120.00, 35.00, -114.04, 42.00),
    ("california", -124.41, 32.53, -114.13, 42.01),
    ("texas", -106.65, 25.84, -93.51, 36.50),
    ("alaska", -179.15, 51.21, -129.98, 71.39),
]


def hav_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def norm_name(s):
    s = (s or "").lower().replace("’", "'").replace("'", "")
    s = s.replace("k-d", "kd").replace("k d", "kd")
    s = re.sub(r"\bmountain bike trail\b", " ", s)
    s = re.sub(r"\bmtb trail\b", " ", s)
    s = re.sub(r"\bbike trail\b", " ", s)
    s = re.sub(r"\btrail\b", " ", s)
    s = re.sub(r"\bthe\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def names_match(a, b):
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    stop = {"park", "loop", "line", "connector", "two", "way"}
    ta = set(na.split()) - stop
    tb = set(nb.split()) - stop
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.67


def grid_key(lat, lon, cell=0.03):
    return (int(math.floor(lat / cell)), int(math.floor(lon / cell)))


def neighbor_keys(lat, lon, cell=0.03):
    gy, gx = grid_key(lat, lon, cell)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            yield (gy + dy, gx + dx)


class SpatialIndex:
    def __init__(self):
        self.cells = defaultdict(list)

    def add(self, trail):
        self.cells[grid_key(trail["lat"], trail["lon"])].append(trail)

    def near(self, lat, lon, miles):
        out = []
        for key in neighbor_keys(lat, lon):
            for t in self.cells.get(key, ()):
                if hav_miles(lat, lon, t["lat"], t["lon"]) <= miles:
                    out.append(t)
        return out


def fnum(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def lookup_state(lat, lon):
    hits = []
    for name, w, s, e, n in STATE_BOXES:
        if w <= lon <= e and s <= lat <= n:
            hits.append(((e - w) * (n - s), name))
    if not hits:
        if lat >= 41 and -141 <= lon <= -52:
            return "canada"
        return ""
    hits.sort()
    return hits[0][1]


def load_json_assign(path):
    text = path.read_text(encoding="utf-8")
    raw = text.split("=", 1)[1].strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    return json.loads(raw)


def ensure_csv():
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 1_000_000:
        return
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        CSV_PATH.write_bytes(resp.read())


def band_for(diff):
    if not diff:
        return None
    return DIFF_MAP.get(str(diff).strip().lower())


def osm_band(tags):
    imba = tags.get("mtb:scale:imba")
    if imba in IMBA:
        return IMBA[imba]
    scale = str(tags.get("mtb:scale") or "").split(";")[0].strip()
    if scale in STS:
        return STS[scale]
    return None


def parse_distance_mi(tags):
    raw = (tags.get("distance") or "").strip().lower()
    m = re.match(r"([0-9]+(?:\.[0-9]+)?)\s*(km|mi|miles|miles)?", raw)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2) or "km"
    if unit == "km":
        val *= 0.621371
    return round(val, 1)


def load_osm_routes():
    routes = []
    seen = set()
    for path in (OSM_CONUS, OSM_NORTH):
        if not path.exists():
            print("missing OSM cache", path)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print("bad OSM json", path, exc)
            continue
        for el in data.get("elements") or []:
            if el.get("type") != "relation":
                continue
            tags = el.get("tags") or {}
            name = (tags.get("name") or "").strip()
            center = el.get("center") or {}
            lat, lon = fnum(center.get("lat")), fnum(center.get("lon"))
            if not name or lat is None or lon is None:
                continue
            if tags.get("proposed") in ("yes", "true") or tags.get("state") == "proposed":
                continue
            oid = el.get("id")
            if oid in seen:
                continue
            seen.add(oid)
            band = osm_band(tags)
            state = lookup_state(lat, lon)
            routes.append({
                "id": f"osm-r{oid}",
                "name": name,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "stars": None,
                "votes": None,
                "difficulty": band,
                "difficulty_band": band,
                "length_mi": parse_distance_mi(tags),
                "location": ("Canada" if state == "canada" else state.title() if state else ""),
                "state": state,
                "source": "openstreetmap",
                "url": f"https://www.openstreetmap.org/relation/{oid}",
                "summary": "Mountain bike route mapped in OpenStreetMap.",
                "year": None,
                "built_or_added": None,
                "geo_source": "OpenStreetMap",
            })
    # Named mtb:scale ways. Segments of one trail become one marker; the same
    # name in a different park (more than ~2.5 miles away) stays separate.
    by_name = defaultdict(list)
    for path in sorted(CACHE.glob("ways_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("skip bad ways file", path)
            continue
        if data.get("remark") and not data.get("elements"):
            print("skip timed-out ways", path, data.get("remark"))
            continue
        for el in data.get("elements") or []:
            tags = el.get("tags") or {}
            name = (tags.get("name") or "").strip()
            center = el.get("center") or {}
            lat, lon = fnum(center.get("lat")), fnum(center.get("lon"))
            if not name or lat is None or lon is None:
                continue
            by_name[norm_name(name)].append((lat, lon, name, tags, el.get("id")))
    for segs in by_name.values():
        clusters = []
        for lat, lon, name, tags, wid in segs:
            placed = False
            for cluster in clusters:
                clat = sum(p[0] for p in cluster) / len(cluster)
                clon = sum(p[1] for p in cluster) / len(cluster)
                if hav_miles(lat, lon, clat, clon) <= 2.5:
                    cluster.append((lat, lon, name, tags, wid))
                    placed = True
                    break
            if not placed:
                clusters.append([(lat, lon, name, tags, wid)])
        for cluster in clusters:
            lat = sum(p[0] for p in cluster) / len(cluster)
            lon = sum(p[1] for p in cluster) / len(cluster)
            # Prefer a segment that actually carries a difficulty tag.
            name, tags, wid = cluster[0][2], cluster[0][3], cluster[0][4]
            for _lat, _lon, n2, t2, w2 in cluster:
                if osm_band(t2) and not osm_band(tags):
                    name, tags, wid = n2, t2, w2
            band = osm_band(tags)
            state = lookup_state(lat, lon)
            routes.append({
                "id": f"osm-w{wid}",
                "name": name,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "stars": None,
                "votes": None,
                "difficulty": band,
                "difficulty_band": band,
                "length_mi": parse_distance_mi(tags),
                "location": "Canada" if state == "canada" else (state.title() if state else ""),
                "state": state,
                "source": "openstreetmap",
                "url": f"https://www.openstreetmap.org/way/{wid}",
                "summary": "Named mountain bike trail from OpenStreetMap (mtb:scale).",
                "year": None,
                "built_or_added": None,
                "geo_source": "OpenStreetMap",
            })
    return routes


def load_ratings():
    rows = []
    if not RATINGS.exists():
        return rows
    for line in RATINGS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("name"):
            rec["name"] = html.unescape(rec["name"])
        if rec.get("summary"):
            rec["summary"] = html.unescape(rec["summary"])
        rows.append(rec)
    return rows


def fetch_kenosha():
    params = {
        "where": "TrailDifficulty IS NOT NULL AND TrailDifficulty <> ''",
        "outFields": "OBJECTID,TRAIL_NAME,ParkName,TrailDifficulty,LENGTH_MI",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "geometryPrecision": "5",
    }
    url = KENOSHA_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("error"):
        raise SystemExit(f"Kenosha GIS error: {data['error']}")
    trails = []
    for feat in data.get("features") or []:
        attr = feat.get("attributes") or {}
        paths = (feat.get("geometry") or {}).get("paths") or []
        pts = [pt for path in paths for pt in path]
        if not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        name = (attr.get("TRAIL_NAME") or "").strip()
        name = re.sub(r"\s+Mountain Bike Trail$", "", name).strip()
        park = (attr.get("ParkName") or "").strip()
        diff_raw = (attr.get("TrailDifficulty") or "").strip().lower()
        band = COUNTY_DIFF.get(diff_raw)
        if "silver lake" in park.lower():
            location = "Salem Lakes, Wisconsin"
        elif "petrif" in park.lower():
            location = "Kenosha, Wisconsin"
        else:
            location = f"{park}, Wisconsin" if park else "Kenosha County, Wisconsin"
        trails.append({
            "id": f"kenosha-{attr.get('OBJECTID')}",
            "name": name or park or "Kenosha County trail",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "stars": None,
            "votes": None,
            "difficulty": band,
            "difficulty_band": band,
            "length_mi": round(fnum(attr.get("LENGTH_MI")) or 0, 2) or None,
            "location": location,
            "state": "wisconsin",
            "source": "county",
            "url": "https://www.kenoshacountywi.gov/2265/Purpose-Built-Mountain-Bike-Trails",
            "summary": f"Purpose-built mountain bike trail at {park or 'a Kenosha County park'}.",
            "year": None,
            "built_or_added": None,
            "geo_source": "Kenosha County GIS",
            "park": park,
        })
    return trails


def attach_ratings(county, ratings):
    used = set()
    for trail in county:
        best = None
        for i, rating in enumerate(ratings):
            if i in used:
                continue
            if not names_match(trail["name"], rating.get("name") or ""):
                continue
            rlat, rlon = fnum(rating.get("lat")), fnum(rating.get("lon"))
            if rlat is None:
                dist = 0
            else:
                dist = hav_miles(trail["lat"], trail["lon"], rlat, rlon)
            if dist > 3:
                continue
            if best is None or dist < best[0]:
                best = (dist, i, rating)
        if not best:
            continue
        _, i, rating = best
        used.add(i)
        stars = fnum(rating.get("stars"))
        votes = rating.get("votes") or 0
        # A 0 with no reviews is "unrated", not a real zero-star score.
        if stars is not None and stars <= 0 and votes <= 0:
            stars = None
        if stars is not None:
            trail["stars"] = round(float(stars), 1)
            trail["votes"] = rating.get("votes")
            trail["rating_source"] = "mtbproject"
        if rating.get("url"):
            trail["url"] = rating["url"]
            m = re.search(r"/trail/(\d+)/", rating["url"])
            if m:
                trail["id"] = f"mtb-{m.group(1)}"
        if rating.get("summary"):
            trail["summary"] = rating["summary"].strip()
        rated_name = (rating.get("name") or "").strip()
        if rated_name and len(rated_name) > len(trail["name"]) + 3 and names_match(trail["name"], rated_name):
            trail["name"] = rated_name
        # Keep the county difficulty; it is the land manager's rating.
        trail["source"] = "mtbproject" if trail.get("stars") is not None else trail["source"]
    extras = []
    for i, rating in enumerate(ratings):
        if i in used:
            continue
        lat, lon = fnum(rating.get("lat")), fnum(rating.get("lon"))
        if lat is None or lon is None or not rating.get("name"):
            continue
        if any(hav_miles(lat, lon, t["lat"], t["lon"]) < 0.15 and names_match(rating["name"], t["name"]) for t in county):
            continue
        band = band_for(rating.get("difficulty"))
        m = re.search(r"/trail/(\d+)/", rating.get("url") or "")
        stars = fnum(rating.get("stars"))
        votes = rating.get("votes") or 0
        if stars is not None and stars <= 0 and votes <= 0:
            stars = None
        extras.append({
            "id": f"mtb-{m.group(1)}" if m else f"mtb-extra-{i}",
            "name": rating["name"],
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "stars": round(float(stars), 1) if stars is not None else None,
            "votes": rating.get("votes") if stars is not None else None,
            "difficulty": band,
            "difficulty_band": band,
            "length_mi": None,
            "location": "Salem Lakes, Wisconsin",
            "state": "wisconsin",
            "source": "mtbproject" if stars is not None else "county",
            "url": rating.get("url"),
            "summary": (rating.get("summary") or "Silver Lake County Park trail.").strip(),
            "year": None,
            "built_or_added": None,
            "geo_source": "MTB Project" if stars is not None else "Kenosha County GIS",
            "rating_source": "mtbproject" if stars is not None else None,
        })
    return county + extras



QUAL_BANDS = {"blue", "blueBlack", "black"}
PLACEHOLDER_SUMMARY = {"needs summary", "to be written"}


def load_baseline():
    """The constrained dataset on main, before this branch widened it."""
    import subprocess
    raw = subprocess.check_output(
        ["git", "show", "main:data/trails.js"], cwd=ROOT
    ).decode("utf-8")
    payload = raw.split("=", 1)[1].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    return json.loads(payload)


def tf_match_keys(trails):
    """Name + coordinates rounded to 0.001° (~100 m). This is the key that
    accounts for the archive rows missing from the baseline MTB set."""
    keys = set()
    for trail in trails:
        if trail.get("source") != "trailforks":
            continue
        keys.add((
            norm_name(trail.get("name")),
            round(float(trail["lat"]), 3),
            round(float(trail["lon"]), 3),
        ))
    return keys


def _votes(raw):
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


def _summary(text):
    summary = (text or "").replace("\n", " ").strip()
    if summary.lower() in PLACEHOLDER_SUMMARY:
        return ""
    return summary


def scan_archive(baseline_ids, tf_keys):
    """Classify every archive row. Add only blue–black ★≥4 trails that are
    not connectors and not already represented."""
    ensure_csv()
    drops = Counter()
    added = []
    with CSV_PATH.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            band = band_for(row.get("difficulty"))
            stars = fnum(row.get("stars")) or 0
            if band not in QUAL_BANDS:
                drops["difficulty_outside_blue_black"] += 1
                continue
            if stars < 4.0:
                drops["blue_black_stars_below_4"] += 1
                continue
            drops["qualifying_archive"] += 1
            if (row.get("type") or "") == "Connector":
                drops["connector"] += 1
                continue
            lat, lon = fnum(row.get("latitude")), fnum(row.get("longitude"))
            if lat is None or lon is None:
                drops["missing_coordinates"] += 1
                continue
            tid = f"mtb-{row['id']}"
            if tid in baseline_ids:
                drops["already_on_baseline"] += 1
                continue
            key = (norm_name(row.get("name")), round(lat, 3), round(lon, 3))
            if key in tf_keys:
                drops["deduped_trailforks"] += 1
                continue
            length = fnum(row.get("length"))
            added.append({
                "id": tid,
                "name": (row.get("name") or "").strip(),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "stars": round(float(stars), 1),
                "votes": _votes(row.get("starVotes")),
                "difficulty": band,
                "difficulty_band": band,
                "length_mi": round(length, 2) if length is not None else None,
                "location": (row.get("location") or "").strip(),
                "state": (row.get("State") or "").strip().lower(),
                "source": "mtbproject",
                "url": (row.get("url") or "").strip() or f"https://www.mtbproject.com/trail/{row['id']}",
                "summary": _summary(row.get("summary")),
                "year": None,
                "built_or_added": None,
            })
            drops["archive_gap_added"] += 1
    return added, drops


def supplemental_pages(existing_ids):
    """MTB Project pages fetched for Silver Lake. Include only blue–black ★≥4."""
    drops = Counter()
    excluded = []
    added = []
    lengths = []
    try:
        lengths = fetch_kenosha()
    except Exception as exc:
        print(f"county length lookup skipped: {exc}")
    for rec in load_ratings():
        band = band_for(rec.get("difficulty"))
        stars = fnum(rec.get("stars")) or 0
        votes = _votes(rec.get("votes"))
        name = (rec.get("name") or "").strip()
        match = re.search(r"/trail/(\d+)/", rec.get("url") or "")
        tid = f"mtb-{match.group(1)}" if match else None
        lat, lon = fnum(rec.get("lat")), fnum(rec.get("lon"))
        detail = {
            "name": name,
            "stars": stars,
            "votes": votes,
            "difficulty": band or rec.get("difficulty"),
        }
        if band not in QUAL_BANDS:
            drops["page_difficulty_outside_blue_black"] += 1
            excluded.append(detail)
            continue
        if stars < 4.0:
            drops["page_stars_below_4"] += 1
            excluded.append(detail)
            continue
        if lat is None or lon is None or not tid:
            drops["page_unusable"] += 1
            continue
        if tid in existing_ids:
            drops["page_already_present"] += 1
            continue
        length = None
        for county in lengths:
            if not names_match(name, county.get("name") or ""):
                continue
            if hav_miles(lat, lon, county["lat"], county["lon"]) > 1.5:
                continue
            length = county.get("length_mi")
            break
        added.append({
            "id": tid,
            "name": name,
            "lat": round(float(lat), 5),
            "lon": round(float(lon), 5),
            "stars": round(float(stars), 1),
            "votes": votes,
            "difficulty": band,
            "difficulty_band": band,
            "length_mi": length,
            "location": "Salem Lakes, Wisconsin",
            "state": "wisconsin",
            "source": "mtbproject",
            "url": rec.get("url"),
            "summary": _summary(rec.get("summary")),
            "year": None,
            "built_or_added": None,
        })
        existing_ids.add(tid)
        drops["stale_extract_added"] += 1
    return added, drops, excluded


def compact(trail):
    """Drop empty optional fields so the browser file stays smaller."""
    out = {
        "id": trail["id"],
        "name": trail["name"],
        "lat": trail["lat"],
        "lon": trail["lon"],
        "stars": trail.get("stars"),
        "votes": trail.get("votes"),
        "difficulty": trail.get("difficulty"),
        "difficulty_band": trail.get("difficulty_band"),
        "length_mi": trail.get("length_mi"),
        "location": trail.get("location") or "",
        "state": trail.get("state") or "",
        "source": trail["source"],
        "url": trail.get("url") or "",
        "summary": trail.get("summary") or "",
        "year": trail.get("year"),
        "built_or_added": trail.get("built_or_added"),
    }
    if trail.get("geo_source"):
        out["geo_source"] = trail["geo_source"]
    if trail.get("rating_source"):
        out["rating_source"] = trail["rating_source"]
    return out


def main():
    started = time.time()
    baseline = load_baseline()
    base = baseline["trails"]
    outside = [
        t for t in base
        if t.get("difficulty_band") not in QUAL_BANDS or (t.get("stars") or 0) < 4
    ]
    if outside:
        raise SystemExit(f"baseline has {len(outside)} trails outside blue–black ★≥4")

    ids = {t["id"] for t in base}
    archive_added, archive_drops = scan_archive(ids, tf_match_keys(base))
    for trail in archive_added:
        ids.add(trail["id"])
    page_added, page_drops, excluded_pages = supplemental_pages(ids)
    trails = [compact(t) for t in (base + archive_added + page_added)]
    trails.sort(key=lambda t: (
        -(t.get("stars") or 0),
        -(t.get("votes") or 0),
        t["name"].lower(),
        t["id"],
    ))

    bad = [
        t for t in trails
        if t.get("difficulty_band") not in QUAL_BANDS or (t.get("stars") or 0) < 4
    ]
    if bad:
        raise SystemExit(f"output has {len(bad)} trails outside the constraint")

    sources = Counter(t["source"] for t in trails)
    bands = Counter(t.get("difficulty_band") or "unknown" for t in trails)
    star_bands = Counter()
    for t in trails:
        s = t.get("stars") or 0
        if s >= 5:
            star_bands["5.0"] += 1
        elif s >= 4.5:
            star_bands["4.5–4.99"] += 1
        elif s >= 4:
            star_bands["4.0–4.49"] += 1
        else:
            star_bands["below 4.0"] += 1

    drops_before = {
        "connector_exclusion": archive_drops["connector"],
        "deduped_same_name_within_0.001deg_of_trailforks": archive_drops["deduped_trailforks"],
        "archive_row_not_on_map": archive_drops["archive_gap_added"],
        "stale_extract_verified_silver_lake_pages": page_drops["stale_extract_added"],
    }
    # After this build those archive gaps and the verified Silver Lake pages are included.
    drops_after = {
        "connector_exclusion": archive_drops["connector"],
        "deduped_same_name_within_0.001deg_of_trailforks": archive_drops["deduped_trailforks"],
        "archive_row_not_on_map": 0,
        "stale_extract_verified_silver_lake_pages": 0,
    }
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone_note": "UTC build; previous file used America/Los_Angeles",
        "sources": {
            "mtbproject": "sgreylewis/mtb-trail-finder US_trails_half_step.csv (committed 2018-01-23) plus public MTB Project trail pages for Silver Lake County Park trails that postdate that archive",
            "trailforks": "Records already on the 2026-09-18 map. Not re-crawled; Trailforks data policy requires their API.",
        },
        "filters_applied": {
            "stars_min": 4.0,
            "difficulty": ["black", "blue", "blueBlack"],
            "excluded": ["doubleBlack", "dblack", "proline", "green", "greenBlue", "white", "connectors"],
        },
        "note_onewheel": "Double-black / proline excluded — not Onewheel-rideable for this map.",
        "coverage_audit": {
            "baseline_count": len(base),
            "qualifying_archive_blue_black_stars_gte_4": archive_drops["qualifying_archive"],
            "drops_before": drops_before,
            "drops_after": drops_after,
            "added_archive_gaps": [t["name"] for t in archive_added],
            "added_stale_extract": [
                {"name": t["name"], "stars": t["stars"], "votes": t["votes"], "difficulty": t["difficulty_band"]}
                for t in page_added
            ],
            "silver_lake_pages_excluded_by_constraint": excluded_pages,
            "archive_rows_outside_difficulty": archive_drops["difficulty_outside_blue_black"],
            "archive_blue_black_below_4": archive_drops["blue_black_stars_below_4"],
        },
        "sources_count": dict(sources),
        "difficulty_count": dict(bands),
        "star_band_count": dict(star_bands),
        "trails": trails,
    }
    text = "window.MTB_TRAILS = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    TRAILS_JS.write_text(text, encoding="utf-8")
    print(f"wrote {len(trails)} trails ({TRAILS_JS.stat().st_size/1e6:.1f} MB) in {time.time()-started:.1f}s")
    print("baseline", len(base), "added archive", len(archive_added), "added pages", len(page_added))
    print("sources", dict(sources))
    print("difficulty", dict(bands))
    print("stars", dict(star_bands))
    print("drops_before", json.dumps(drops_before))
    print("drops_after", json.dumps(drops_after))
    print("archive outside difficulty", archive_drops["difficulty_outside_blue_black"], "blue-black below 4", archive_drops["blue_black_stars_below_4"])
    print("excluded silver lake pages", excluded_pages)
    print("added", [(t["name"], t["stars"], t["votes"], t["difficulty_band"], t["length_mi"]) for t in archive_added + page_added])

    regions = {
        "silver_lake_park": (42.545, -88.155, 42.570, -88.120),
        "salem_lakes": (42.50, -88.25, 42.62, -88.05),
        "moab": (38.45, -109.80, 38.75, -109.35),
        "bentonville": (36.30, -94.30, 36.50, -94.05),
        "kingdom_trails": (44.52, -71.98, 44.68, -71.75),
        "copper_harbor": (47.42, -87.95, 47.50, -87.80),
        "pisgah": (35.15, -82.85, 35.45, -82.55),
    }
    print("\nregion baseline -> after (4.5+ in the new box)")
    for name, (a, b, c, d) in regions.items():
        old = [t for t in base if a <= t["lat"] <= c and b <= t["lon"] <= d]
        new = [t for t in trails if a <= t["lat"] <= c and b <= t["lon"] <= d]
        hi = sum(1 for t in new if (t.get("stars") or 0) >= 4.5)
        print(f"  {name:20} {len(old):5} -> {len(new):5}  (4.5+ {hi})")
        if name in ("silver_lake_park", "salem_lakes"):
            for t in sorted(new, key=lambda r: -(r.get("stars") or 0)):
                print(f"    {t.get('stars')} v{t.get('votes')} {t.get('difficulty_band')} {t['source']:12} {t['name']} | {t.get('location')}")


if __name__ == "__main__":
    main()
