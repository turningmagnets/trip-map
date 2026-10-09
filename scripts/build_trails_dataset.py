#!/usr/bin/env python3
"""Build normalized trails.json / trails.js + ride-recording export (v2, stars >= 3.8).

Inputs (all local cache, nothing fetched):
  raw/US_trails_half_step.csv                    MTB Project archive (points only)
  cache/trailforks/v2_details.json               every cached TF detail page (scripts/parse_cache_v2.py)
  cache/trailforks/v2_cards.json                 every cached TF directory card
  cache/trailforks/v2_region_rows.json           every cached TF state region-table row (votes, no stars)
  raw/trailforks_curated.json                    hand-curated TF pages (optional)
  cache/trailforks/v3_browser_crawl.json         2026-10 browser pass (scripts/merge_crawl_results.py);
                                                 set NO_CRAWL=1 to build without it

Rating basis
  Trailforks: the rating shown on the trail page (Bayesian, e.g. "3.86 / 5 with 11 votes").
    If only a directory card exists we use the card's raw average (always <= as permissive
    as the Bayesian figure for >= 3.8, so nothing is invented).
  MTB Project: archive star average.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path("/workspace/mtb-trails-map")
RAW_CSV = ROOT / "raw" / "US_trails_half_step.csv"
TFC = ROOT / "cache" / "trailforks"
TF_DETAILS = TFC / "v2_details.json"
TF_CARDS = TFC / "v2_cards.json"
TF_REGION = TFC / "v2_region_rows.json"
TF_CURATED = ROOT / "raw" / "trailforks_curated.json"
TF_CRAWL = TFC / "v3_browser_crawl.json"
OUT = Path(os.environ.get("TRAILS_OUT") or (ROOT / "data"))
USE_CRAWL = os.environ.get("NO_CRAWL") != "1"

STARS_MIN = 3.8
ALLOWED = {"blue", "blueBlack", "black"}
TF_DIFF = {1: "access", 2: "white", 3: "green", 4: "blue", 5: "black", 6: "doubleBlack", 8: "proline", 11: "access"}

US_STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
STATES = set(US_STATE_ABBR.values())
CA_OK = {"British Columbia", "Alberta"}
SLUG_STATE = {s.lower().replace(" ", "-"): s for s in STATES | CA_OK}


def norm_state(s):
    if not s:
        return None
    s = s.strip()
    if s.upper() in US_STATE_ABBR:
        return US_STATE_ABBR[s.upper()]
    t = s.replace("-", " ").title()
    for full in STATES | CA_OK:
        if full.lower() == t.lower():
            return full
    return t


def hav_km(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def simplify(pts, tol_m=8.0):
    """Douglas-Peucker in a local equirectangular projection."""
    if len(pts) < 3:
        return pts
    lat0 = math.radians(pts[0][0])
    xy = [(p[1] * 111320 * math.cos(lat0), p[0] * 110540) for p in pts]

    def rec(i, j, keep):
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        best, bi = -1, None
        for k in range(i + 1, j):
            x, y = xy[k]
            if L == 0:
                d = math.hypot(x - x1, y - y1)
            else:
                t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L))
                d = math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
            if d > best:
                best, bi = d, k
        if best > tol_m:
            keep.add(bi)
            rec(i, bi, keep)
            rec(bi, j, keep)

    keep = {0, len(pts) - 1}
    import sys
    sys.setrecursionlimit(10000)
    rec(0, len(pts) - 1, keep)
    return [pts[k] for k in sorted(keep)]


def encode_polyline(pts):
    out, plat, plon = [], 0, 0
    for lat, lon in pts:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


# ---------------------------------------------------------------- MTB Project
def load_mtb(funnel, other):
    trails = []
    with RAW_CSV.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            funnel["mtb_rows"] += 1
            try:
                stars = float(row["stars"])
            except (KeyError, ValueError):
                funnel["mtb_drop_no_rating"] += 1
                continue
            if stars == 0:
                funnel["mtb_drop_unrated(0)"] += 1
                continue
            if stars < STARS_MIN:
                funnel["mtb_drop_below_3.8"] += 1
                continue
            try:
                lat, lon = float(row["latitude"]), float(row["longitude"])
            except (TypeError, ValueError):
                funnel["mtb_drop_no_coords"] += 1
                continue
            diff = (row.get("difficulty") or "").strip()
            typ = (row.get("type") or "").strip()
            votes = int(float(row.get("starVotes") or 0))
            try:
                length = float(row.get("length") or 0) or None
            except ValueError:
                length = None
            loc = (row.get("location") or "").strip() or None
            rec = {
                "id": f"mtb-{row['id']}",
                "name": (row.get("name") or f"Trail {row['id']}").strip(),
                "lat": lat, "lon": lon,
                "stars": stars, "stars_basis": "mtbproject_avg", "votes": votes,
                "difficulty": diff, "difficulty_band": diff,
                "length_mi": length, "location": loc,
                "state": norm_state(row.get("State")) or None,
                "country": "United States",
                "source": "mtbproject", "url": row.get("url") or "",
                "summary": row.get("summary") or None,
                "mtb_type": typ,
                "built_or_added": None, "year": None,
                "geometry": "point_trailhead",
            }
            if diff not in ALLOWED:
                funnel[f"mtb_drop_difficulty_{diff or 'missing'}"] += 1
                rec["excluded_reason"] = f"difficulty={diff or 'missing'}"
                other.append(rec)
                continue
            if typ.lower() == "connector":
                funnel["mtb_drop_connector"] += 1
                rec["excluded_reason"] = "mtbproject type=Connector"
                other.append(rec)
                continue
            trails.append(rec)
    extra = ROOT / "raw" / "mtbproject_extra_pages.json"
    if extra.exists():
        have = {t["id"] for t in trails}
        for t in json.loads(extra.read_text())["trails"]:
            if t["id"] in have or t["stars"] < STARS_MIN or t["difficulty_band"] not in ALLOWED:
                continue
            trails.append({**t, "stars_basis": "mtbproject_page", "country": "United States", "mtb_type": None,
                           "geometry": "point_trailhead"})
            funnel["mtb_extra_pages_kept"] += 1
    funnel["mtb_kept"] = len(trails)
    return trails


# ---------------------------------------------------------------- Trailforks
def geo_ok(country, state, lat):
    c = (country or "").lower()
    if c in ("united states", "usa", "us"):
        return True
    if c == "canada":
        return state in CA_OK
    if not c:
        return state in STATES or state in CA_OK
    return False


def load_tf(funnel, other, region_rows, crawl=None):
    crawl = crawl or {}
    details = [d for d in json.loads(TF_DETAILS.read_text())]
    cards = {c["trailforks_id"]: c for c in json.loads(TF_CARDS.read_text())}
    out = {}
    detail_ids = set()
    for d in details:
        funnel["tf_detail_pages"] += 1
        if "error" in d:
            funnel["tf_detail_unparseable(Error page)"] += 1
            continue
        tid = d["trailforks_id"]
        detail_ids.add(tid)
        dn = d.get("diff_num") or d.get("diff_num_top")
        band = TF_DIFF.get(dn, f"tf{dn}")
        stars = d.get("vis_stars") or d.get("stars_bayes")
        raw = (d.get("rating_pct") or 0) / 20 or None
        votes = d.get("vis_votes") if d.get("vis_votes") is not None else d.get("votes")
        state = norm_state(d.get("prov"))
        rr = region_rows.get(tid)
        c = crawl.get(tid)
        if c:  # browser-crawl values win where real
            stars = c["stars"] if c["stars"] is not None else stars
            votes = c["votes"] if c["votes"] is not None else votes
            if c["band"]:
                band = c["band"]
            if c["th_lat"] is not None:
                d = {**d, "lat": c["th_lat"], "lon": c["th_lon"]}
            if c["closed"] is not None:
                d = {**d, "closed": "1" if c["closed"] else "0"}
            if c["riding_area"]:
                d = {**d, "ridingarea": c["riding_area"]}
            funnel["crawl_overlay_on_detail_page"] += 1
        if not stars:
            funnel["tf_detail_drop_no_rating"] += 1
            continue
        if stars < STARS_MIN:
            funnel["tf_detail_drop_below_3.8"] += 1
            continue
        if d.get("lat") is None:
            funnel["tf_detail_drop_no_coords"] += 1
            continue
        if not geo_ok(d.get("country"), state, d["lat"]):
            funnel[f"tf_detail_drop_outside_US_BC_AB"] += 1
            continue
        line = [tuple(p) for p in d.get("line") or []]
        rec = {
            "id": f"tf-{tid}",
            "name": d.get("name") or f"Trailforks {tid}",
            "lat": d["lat"], "lon": d["lon"],
            "stars": round(stars, 2), "stars_basis": "trailforks_page_bayesian",
            "stars_raw_avg": round(raw, 2) if raw else None,
            "votes": int(votes or 0),
            "difficulty": band, "difficulty_band": band,
            "length_mi": round(d["distance_m"] / 1609.34, 2) if d.get("distance_m") else None,
            "location": ", ".join(x for x in (d.get("city"), d.get("prov")) if x) or None,
            "riding_area": d.get("ridingarea") or d.get("region_name"),
            "state": state, "country": d.get("country"),
            "source": "trailforks",
            "url": f"https://www.trailforks.com/trails/{d['alias']}/" if d.get("alias") else (rr or {}).get("url", ""),
            "summary": d.get("description"),
            "built_or_added": datetime.utcfromtimestamp(d["created"]).date().isoformat() if d.get("created") else None,
            "year": datetime.utcfromtimestamp(d["created"]).year if d.get("created") else None,
            "closed": d.get("closed") == "1",
            "unsanctioned": d.get("unsanctioned") == "1",
            "archived": d.get("archived") == "1",
            "direction": {"1": "downhill_only", "2": "downhill_primary", "3": "both", "4": "uphill_primary", "5": "uphill_only", "6": "one_direction"}.get(str(d.get("direction")), None),
            "_line": line,
            "geometry": "line" if len(line) >= 2 else "point_start",
        }
        if c and c["th_lat"] is not None:
            rec["trailhead_lat"], rec["trailhead_lon"] = c["th_lat"], c["th_lon"]
        if c:
            rec["crawl_batch"] = c["batch"]
        if band not in ALLOWED:
            funnel[f"tf_detail_drop_difficulty_{band}"] += 1
            rec["excluded_reason"] = f"difficulty={band}"
            other.append(rec)
            continue
        out[tid] = rec
    funnel["tf_detail_kept"] = len(out)

    # Directory cards without a detail page
    for tid, c in cards.items():
        if tid in detail_ids:
            continue
        funnel["tf_card_only"] += 1
        cc = crawl.get(tid)
        if cc:  # page rating from the browser pass beats the card's raw average
            c = dict(c)
            if cc["stars"] is not None:
                c["stars"], c["_basis"] = cc["stars"], "trailforks_page_bayesian"
            if cc["th_lat"] is not None:
                c["lat"], c["lon"] = cc["th_lat"], cc["th_lon"]
            funnel["crawl_overlay_on_card"] += 1
        if c.get("stars") is None or c.get("stars") == 0:
            funnel["tf_card_drop_unrated"] += 1
            continue
        if c["stars"] < STARS_MIN:
            funnel["tf_card_drop_below_3.8"] += 1
            continue
        if c.get("lat") is None:
            funnel["tf_card_drop_no_coords"] += 1
            continue
        dn = c.get("diff_num")
        title = (c.get("diff_title") or "").lower()
        band = TF_DIFF.get(dn) if dn else None
        if not band:
            band = "blue" if "intermediate" in title else "black" if "very difficult" in title else "green" if "green" in title else ("doubleBlack" if "dbl" in title else "unknown")
        rr = region_rows.get(tid) or {}
        loc = c.get("location")
        state = None
        if rr.get("state_slug"):
            state = SLUG_STATE.get(rr["state_slug"])
        if not state and loc:
            mab = re.search(r",\s*([A-Z]{2})\s*$", loc)
            if mab:
                state = US_STATE_ABBR.get(mab.group(1)) or {"BC": "British Columbia", "AB": "Alberta"}.get(mab.group(1))
        if not state and loc:
            for s in STATES | CA_OK:
                if loc.endswith(s) or f", {s}" in loc:
                    state = s
        if not (24 <= c["lat"] <= 61 and -170 <= c["lon"] <= -50):
            funnel["tf_card_drop_outside_US_BC_AB"] += 1
            continue
        if not state or (state not in STATES and state not in CA_OK):
            funnel["tf_card_drop_outside_US_BC_AB"] += 1
            continue
        rec = {
            "id": f"tf-{tid}", "name": c.get("name") or f"Trailforks {tid}",
            "lat": c["lat"], "lon": c["lon"],
            "stars": round(c["stars"], 2), "stars_basis": c.get("_basis") or "trailforks_card_raw_avg",
            "stars_raw_avg": None if c.get("_basis") else c["stars"],
            "votes": rr.get("votes") or 0,
            "difficulty": band, "difficulty_band": band,
            "length_mi": None, "location": loc, "riding_area": rr.get("area"),
            "state": state, "country": None, "source": "trailforks",
            "url": c.get("url") or rr.get("url", ""), "summary": None,
            "built_or_added": None, "year": None,
            "closed": bool(rr.get("closed")), "unsanctioned": None, "archived": None, "direction": None,
            "_line": [], "geometry": "point_start",
        }
        if cc:
            if cc["votes"] is not None:
                rec["votes"] = cc["votes"]
            if cc["band"]:
                rec["difficulty"] = rec["difficulty_band"] = band = cc["band"]
            if cc["riding_area"]:
                rec["riding_area"] = cc["riding_area"]
            if cc["closed"] is not None:
                rec["closed"] = cc["closed"]
            if cc["th_lat"] is not None:
                rec["trailhead_lat"], rec["trailhead_lon"] = cc["th_lat"], cc["th_lon"]
            rec["crawl_batch"] = cc["batch"]
        if band not in ALLOWED:
            funnel[f"tf_card_drop_difficulty_{band}"] += 1
            rec["excluded_reason"] = f"difficulty={band}"
            other.append(rec)
            continue
        out[tid] = rec
        funnel["tf_card_kept"] += 1

    # Browser-crawl trails with no cached detail page or card (the gap worklist)
    crawl_resolved = set()
    for tid, c in crawl.items():
        if tid in detail_ids or tid in cards:
            continue
        funnel["crawl_new_rows"] += 1
        if c["stars"] is None:
            funnel["crawl_new_held_bad_or_missing_rating"] += 1
            continue
        if c["th_lat"] is None:
            funnel["crawl_new_held_no_coords"] += 1
            continue
        crawl_resolved.add(tid)
        if c["stars"] < STARS_MIN:
            funnel["crawl_new_drop_below_3.8"] += 1
            continue
        rr = region_rows.get(tid) or {}
        state = SLUG_STATE.get(rr.get("state_slug") or "") or norm_state(c.get("queue_state"))
        if not state or (state not in STATES and state not in CA_OK):
            funnel["crawl_new_drop_outside_US_BC_AB"] += 1
            continue
        band = c["band"]
        if not band:
            t = (rr.get("diff_title") or "").lower()
            band = "blue" if "intermediate" in t else "black" if "very difficult" in t else "unknown"
        votes = c["votes"] if c["votes"] is not None else (rr.get("votes") or 0)
        closed = c["closed"] if c["closed"] is not None else bool(rr.get("closed"))
        rec = {
            "id": f"tf-{tid}", "name": c["name"] or rr.get("name") or f"Trailforks {tid}",
            "lat": c["th_lat"], "lon": c["th_lon"],
            "trailhead_lat": c["th_lat"], "trailhead_lon": c["th_lon"],
            "end_lat": c["end_lat"], "end_lon": c["end_lon"],
            "stars": round(c["stars"], 2), "stars_basis": "trailforks_page_bayesian", "stars_raw_avg": None,
            "votes": int(votes), "difficulty": band, "difficulty_band": band,
            "length_mi": None, "location": None, "riding_area": c["riding_area"] or rr.get("area"),
            "state": state, "country": None, "source": "trailforks",
            "url": c["url"] or rr.get("url", ""), "summary": None, "built_or_added": None, "year": None,
            "closed": closed, "unsanctioned": None, "archived": None, "direction": None,
            "_line": [], "geometry": "point_trailhead", "crawl_batch": c["batch"],
        }
        if band not in ALLOWED:
            funnel[f"crawl_new_drop_difficulty_{band}"] += 1
            rec["excluded_reason"] = f"difficulty={band}"
            other.append(rec)
            continue
        out[tid] = rec
        funnel["crawl_new_kept"] += 1
    load_tf.crawl_resolved = crawl_resolved

    # Curated (hand-checked) pages
    if TF_CURATED.exists():
        cur = json.loads(TF_CURATED.read_text())
        for t in cur if isinstance(cur, list) else cur.get("trails", []):
            tid = str(t.get("trailforks_id") or str(t.get("id", "")).replace("tf-", ""))
            if not tid or tid in out or tid in crawl or t.get("exclude"):
                continue
            try:
                stars = float(t.get("stars") or 0)
                lat, lon = float(t["lat"]), float(t["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            band = t.get("difficulty_band") or t.get("difficulty")
            if stars < STARS_MIN or band not in ALLOWED:
                continue
            cst = norm_state(t.get("state"))
            if cst in ("Bc", "BC"):
                cst = "British Columbia"
            if cst not in STATES and cst not in CA_OK:
                funnel["tf_curated_drop_outside_US_BC_AB"] += 1  # e.g. Manitoba, Japan entries
                continue
            t = {**t, "state": cst}
            out[tid] = {**{k: t.get(k) for k in ("name", "length_mi", "location", "summary", "built_or_added", "year")},
                        "id": f"tf-{tid}", "lat": lat, "lon": lon, "stars": stars, "stars_basis": "trailforks_curated",
                        "votes": int(t.get("votes") or 0), "difficulty": band, "difficulty_band": band,
                        "state": norm_state(t.get("state")), "source": "trailforks", "url": t.get("url", ""),
                        "_line": [], "geometry": "point_start"}
            funnel["tf_curated_kept"] += 1
    return list(out.values()), detail_ids, cards


# ---------------------------------------------------------------- dedupe
STOP = {"trail", "trails", "the", "loop", "tr", "mtb", "path", "singletrack"}


def norm_name(n):
    n = (n or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"#\s*\w+", " ", n)
    n = n.replace("&", " and ")
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    toks = [t for t in n.split() if t not in STOP]
    return " ".join(toks)


def min_dist_km(lat, lon, rec):
    pts = rec["_line"] or [(rec["lat"], rec["lon"])]
    step = max(1, len(pts) // 60)
    return min(hav_km(lat, lon, p[0], p[1]) for p in pts[::step] + [pts[-1]])


def dedupe(mtb, tf, funnel):
    grid = defaultdict(list)
    for r in tf:
        grid[(round(r["lat"] * 20), round(r["lon"] * 20))].append(r)
    merged_ids = []
    kept_mtb = []
    for m in mtb:
        nm = norm_name(m["name"])
        best = None
        gy, gx = round(m["lat"] * 20), round(m["lon"] * 20)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for r in grid.get((gy + dy, gx + dx), []):
                    nr = norm_name(r["name"])
                    if not nm or not nr:
                        continue
                    if re.findall(r"\d+", nm) != re.findall(r"\d+", nr):
                        continue  # "Section 1" vs "Section 2" are different trails
                    sim = 1.0 if nm == nr else SequenceMatcher(None, nm, nr).ratio()
                    if sim < 0.9:
                        continue
                    dist = min_dist_km(m["lat"], m["lon"], r)
                    if dist > 1.0:
                        continue
                    score = (sim, -dist)
                    if not best or score > best[0]:
                        best = (score, r, dist)
        if best:
            r = best[1]
            r.setdefault("alt_ids", []).append(m["id"])
            r.setdefault("alt_urls", []).append(m["url"])
            r.setdefault("alt_points", []).append([m["lat"], m["lon"]])
            if m.get("stars") is not None:
                r.setdefault("alt_stars", []).append(m["stars"])
            merged_ids.append((m["id"], r["id"], round(best[2], 3), m["name"], r["name"]))
            funnel["dedupe_mtb_merged_into_tf"] += 1
        else:
            kept_mtb.append(m)
    return kept_mtb, merged_ids


def band_label(s):
    if s >= 5:
        return "5.0"
    if s >= 4.5:
        return "4.5–4.99"
    if s >= 4.0:
        return "4.0–4.49"
    return "3.8–3.99"


def main():
    funnel = Counter()
    other = []
    region_rows = {r["trailforks_id"]: r for r in json.loads(TF_REGION.read_text())}
    mtb = load_mtb(funnel, other)
    crawl = {}
    if USE_CRAWL and TF_CRAWL.exists():
        crawl = {c["trailforks_id"]: c for c in json.loads(TF_CRAWL.read_text())}
    funnel["crawl_rows_loaded"] = len(crawl)
    tf, detail_ids, cards = load_tf(funnel, other, region_rows, crawl)
    crawl_resolved = getattr(load_tf, "crawl_resolved", set())
    mtb_kept, merges = dedupe(mtb, tf, funnel)
    trails = tf + mtb_kept
    trails.sort(key=lambda t: (-t["stars"], -(t["votes"] or 0), t["name"]))

    by_src = Counter(t["source"] for t in trails)
    by_diff = Counter(t["difficulty_band"] for t in trails)
    by_star = Counter(band_label(t["stars"]) for t in trails)
    by_geom = Counter(t["geometry"] for t in trails)
    votes10 = [t for t in trails if (t["votes"] or 0) >= 10]

    # ---- map payload (points only; keep phone payload small)
    keep_keys = ("id", "name", "lat", "lon", "stars", "votes", "difficulty", "difficulty_band", "length_mi",
                 "location", "state", "source", "url", "summary", "built_or_added", "year", "alt_ids")
    map_trails = []
    for t in trails:
        m = {k: t.get(k) for k in keep_keys if t.get(k) is not None}
        if m.get("summary") and len(m["summary"]) > 300:
            m["summary"] = m["summary"][:297] + "..."
        if t.get("closed"):
            m["closed"] = True
        map_trails.append(m)
    payload = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {
            "mtbproject": "sgreylewis/mtb-trail-finder US_trails_half_step.csv archive (c. 2020)",
            "trailforks": "Cached public HTML: detail pages + directory cards + state region tables (crawled Sep 2026)",
        },
        "filters_applied": {
            "stars_min": STARS_MIN,
            "difficulty": sorted(ALLOWED),
            "excluded": ["doubleBlack", "dblack", "proline", "green", "greenBlue", "white", "MTB Project connectors"],
            "stars_basis": "Trailforks page (Bayesian) rating; card raw avg if no detail page; MTB Project avg",
        },
        "note_onewheel": "Double-black / proline excluded — not Onewheel-rideable for this map.",
        "sources_count": dict(by_src),
        "difficulty_count": dict(by_diff),
        "star_band_count": dict(by_star),
        "geometry_count": dict(by_geom),
        "votes_ge_10": len(votes10),
        "trailforks_year_ge_2021": sum(1 for t in trails if t["source"] == "trailforks" and (t.get("year") or 0) >= 2021),
        "trails": map_trails,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "trails.json").write_text(json.dumps(payload, indent=1))
    (OUT / "trails.js").write_text("window.MTB_TRAILS = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    (OUT / "mtbproject_only.json").write_text(json.dumps({"trails": mtb, "count": len(mtb)}, indent=1))

    # ---- ride-recording export (all >=3.8, no vote filter)
    def export_rec(t, include_reason=False):
        """lat/lon = the trigger point for the ride-recording tool: the trailhead / start.
        Priority: Trailforks page trailhead (browser crawl) > first point of the GPS track >
        TF card start point > MTB Project trailhead point."""
        line = simplify(t.get("_line") or [], 8.0)
        if t.get("trailhead_lat") is not None:
            plat, plon, basis = t["trailhead_lat"], t["trailhead_lon"], "tf_page_trailhead"
        elif line:
            plat, plon, basis = line[0][0], line[0][1], "tf_track_start"
        elif t["source"] == "mtbproject":
            plat, plon, basis = t["lat"], t["lon"], "mtbproject_trailhead"
        else:
            plat, plon, basis = t["lat"], t["lon"], ("tf_curated_point" if t.get("stars_basis") == "trailforks_curated"
                                                     else "tf_card_start")
        e = {
            "id": t["id"], "source": t["source"], "source_url": t["url"], "name": t["name"],
            "lat": plat, "lon": plon, "point_basis": basis,
            "geometry": t["geometry"],
            "start_lat": line[0][0] if line else plat, "start_lon": line[0][1] if line else plon,
            "end_lat": line[-1][0] if line else t.get("end_lat"), "end_lon": line[-1][1] if line else t.get("end_lon"),
            "line": [[round(a, 5), round(b, 5)] for a, b in line] if line else None,
            "line_points_full": len(t.get("_line") or []),
            "length_mi": t.get("length_mi"),
            "stars": t["stars"], "stars_basis": t.get("stars_basis"), "stars_raw_avg": t.get("stars_raw_avg"),
            "votes": t["votes"], "difficulty": t["difficulty_band"],
            "riding_area": t.get("riding_area"), "location": t.get("location"),
            "state": t.get("state"), "country": t.get("country"),
            "direction": t.get("direction"), "closed": t.get("closed"),
            "also_listed_as": t.get("alt_ids"), "also_listed_urls": t.get("alt_urls"),
            "also_listed_points": t.get("alt_points"),
        }
        if include_reason:
            e["excluded_reason"] = t.get("excluded_reason")
        return e

    exp = [export_rec(t) for t in trails]
    meta = {
        "generated": payload["generated"],
        "description": "All trails rated >= 3.8 stars (blue / blue-black / black), no vote filter. "
                       "geometry=line -> 'line' is the Trailforks GPS track (Douglas-Peucker 8 m). "
                       "point_trailhead -> one trailhead/start point only (MTB Project archive, or the Trailforks "
                       "trail page trailhead from the 2026-10 browser pass). "
                       "point_start -> Trailforks directory card start point only. "
                       "lat/lon is always the trailhead/start trigger point; point_basis says where it came from.",
        "count": len(exp),
        "sources_count": dict(by_src), "geometry_count": dict(by_geom),
        "point_basis_count": dict(Counter(e["point_basis"] for e in exp)),
    }
    (OUT / "trails_export.json").write_text(json.dumps({**meta, "trails": exp}, separators=(",", ":")))
    cols = ["id", "source", "source_url", "name", "lat", "lon", "geometry", "start_lat", "start_lon", "end_lat", "end_lon",
            "line_polyline", "length_mi", "stars", "stars_basis", "stars_raw_avg", "votes", "difficulty", "riding_area",
            "location", "state", "country", "direction", "closed", "also_listed_as", "point_basis"]
    with (OUT / "trails_export.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in exp:
            row = {k: e.get(k) for k in cols if k in e}
            row["line_polyline"] = encode_polyline(e["line"]) if e["line"] else ""
            row["also_listed_as"] = ";".join(e["also_listed_as"] or [])
            w.writerow(row)

    # ---- supplementary: >=3.8 trails dropped ONLY by difficulty / connector rules
    oth = [export_rec(t, True) for t in other]
    (OUT / "trails_export_other_difficulty.json").write_text(json.dumps({
        "generated": payload["generated"],
        "description": "NOT on the map. Trails rated >= 3.8 that the map's difficulty rules exclude "
                       "(green, greenBlue, double-black, proline, MTB Project 'Connector' type). For recall only.",
        "count": len(oth), "reasons": dict(Counter(o["excluded_reason"] for o in oth)), "trails": oth}, separators=(",", ":")))
    with (OUT / "trails_export_other_difficulty.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols + ["excluded_reason"])
        w.writeheader()
        for e in oth:
            row = {k: e.get(k) for k in cols + ["excluded_reason"] if k in e}
            row["line_polyline"] = encode_polyline(e["line"]) if e["line"] else ""
            row["also_listed_as"] = ""
            w.writerow(row)

    # ---- gap worklist: TF blue/black trails in region tables with votes but no rating/coords in cache
    have = {t["id"][3:] for t in trails if t["source"] == "trailforks"} | detail_ids | set(cards) | crawl_resolved
    gap = []
    for tid, r in region_rows.items():
        title = (r.get("diff_title") or "").lower()
        band = "blue" if "intermediate" in title else "black" if "very difficult" in title else None
        if not band or tid in have or (r.get("votes") or 0) < 1:
            continue
        gap.append({"trailforks_id": tid, "name": r["name"], "url": r["url"], "votes": r["votes"], "difficulty": band,
                    "riding_area": r.get("area"), "state": SLUG_STATE.get(r["state_slug"], r["state_slug"]),
                    "closed": r.get("closed")})
    gap.sort(key=lambda g: (-g["votes"], g["state"], g["name"]))
    with (OUT / "trailforks_gap_worklist.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gap[0].keys()))
        w.writeheader()
        w.writerows(gap)

    (OUT / "dedupe_merges.csv").write_text("mtb_id,tf_id,dist_km,mtb_name,tf_name\n" + "\n".join(
        ",".join(json.dumps(x) if isinstance(x, str) else str(x) for x in m) for m in merges) + "\n")
    stats = {
        "total": len(trails), "sources": dict(by_src), "difficulty": dict(by_diff), "stars": dict(by_star),
        "geometry": dict(by_geom), "votes_ge_10": len(votes10),
        "votes_ge_10_by_source": dict(Counter(t["source"] for t in votes10)),
        "other_difficulty_supplement": len(oth), "gap_worklist": len(gap),
        "gap_by_votes": dict(Counter("1-4" if g["votes"] < 5 else "5-9" if g["votes"] < 10 else "10+" for g in gap)),
        "browser_crawl": {
            "rows_loaded": len(crawl),
            "new_kept_on_map": funnel["crawl_new_kept"],
            "new_kept_merged_mtbproject_points": sum(1 for t in trails if t.get("crawl_batch") and t.get("alt_ids")),
            "new_below_3.8": funnel["crawl_new_drop_below_3.8"],
            "new_other_difficulty": sum(v for k, v in funnel.items() if k.startswith("crawl_new_drop_difficulty_")),
            "held_no_coords": funnel["crawl_new_held_no_coords"],
            "held_bad_or_missing_rating": funnel["crawl_new_held_bad_or_missing_rating"],
            "overlay_on_cached_detail_or_card": funnel["crawl_overlay_on_detail_page"] + funnel["crawl_overlay_on_card"],
            "on_map_by_star_band": dict(Counter(band_label(t["stars"]) for t in trails if t.get("crawl_batch"))),
            "on_map_by_difficulty": dict(Counter(t["difficulty_band"] for t in trails if t.get("crawl_batch"))),
        } if crawl else None,
        "funnel": dict(sorted(funnel.items())),
    }
    (OUT / "build_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
