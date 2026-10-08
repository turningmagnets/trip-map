#!/usr/bin/env python3
"""Re-parse the ENTIRE cached Trailforks crawl with no star/vote filters.

Outputs cache/trailforks/v2_details.json, v2_cards.json, v2_region_rows.json.
Nothing is fetched from the network.
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path("/workspace/mtb-trails-map")
CACHE = ROOT / "cache" / "trailforks"

# Trailforks difficulty ids (about/metadata): 1 access road, 2 white/easiest, 3 green/easy,
# 4 blue/intermediate, 5 black/very difficult, 6 dbl black, 8 proline, 11 secondary access, 7/9 ?
TF_DIFF = {1: "access", 2: "white", 3: "green", 4: "blue", 5: "black", 6: "doubleBlack", 8: "proline", 11: "access"}


def decode_polyline(s: str, precision: int = 5):
    coords, index, lat, lng = [], 0, 0, 0
    factor = 10 ** precision
    while index < len(s):
        for which in (0, 1):
            shift = result = 0
            while True:
                if index >= len(s):
                    return coords
                b = ord(s[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else (result >> 1)
            if which == 0:
                lat += d
            else:
                lng += d
        coords.append((lat / factor, lng / factor))
    return coords


def parse_detail_file(path: str):
    try:
        html = Path(path).read_text(errors="replace")
    except Exception as e:  # pragma: no cover
        return {"file": path, "error": str(e)}
    tid = Path(path).stem
    if "var trail" not in html:
        title = re.search(r"<title>([^<]*)", html)
        return {"file": path, "trailforks_id": tid, "error": "no_trail_json", "title": title.group(1)[:80] if title else None, "size": len(html)}
    m = re.search(r"var trail\s*=\s*(\[\{.*?\}\]);", html, re.S)
    try:
        d = json.loads(m.group(1))[0]
    except Exception:
        return {"file": path, "trailforks_id": tid, "error": "bad_json"}
    act = None
    ad = d.get("activity_details")
    if isinstance(ad, dict):
        act = ad.get("1")
    act = act if isinstance(act, dict) else {}
    cur = d.get("current_activity_details") if isinstance(d.get("current_activity_details"), dict) else {}

    def num(*vals, cast=float):
        for v in vals:
            try:
                x = cast(v)
                if x or x == 0:
                    return x
            except (TypeError, ValueError):
                pass
        return None

    diff_num = num(act.get("difficulty"), d.get("difficulty"), cast=int)
    stars = None
    for v in (act.get("rating_bayesian"), d.get("rating_bayesian")):
        try:
            x = float(v)
            if x > 0:
                stars = x
                break
        except (TypeError, ValueError):
            pass
    votes = num(act.get("rating_votes"), act.get("votes"), d.get("votes"), cast=int) or 0
    # Visible star widget for this trail: "<x> / 5 with <n> votes" on ul id=trail_<tid>
    vis = re.search(rf'id="trail_{tid}"[^>]*title="([0-9.]+)\s*/\s*5 with (\d+) votes?"', html)
    vis_stars = vis_votes = None
    if vis:
        vis_stars, vis_votes = float(vis.group(1)), int(vis.group(2))
    # geometry
    line = []
    me = re.search(r"geometry:\s*\{\s*type:\s*'LineString',\s*encodedpath:\s*'((?:[^'\\]|\\.)*)'", html)
    if me:
        enc = me.group(1).encode().decode("unicode_escape")
        line = decode_polyline(enc)
    try:
        lat, lon = float(d.get("latitude")), float(d.get("longitude"))
    except (TypeError, ValueError):
        lat = lon = None
    created = num(d.get("created"), cast=int)
    return {
        "trailforks_id": str(d.get("trailid") or tid),
        "name": d.get("title"),
        "alias": d.get("alias"),
        "lat": lat,
        "lon": lon,
        "stars_bayes": round(stars, 3) if stars else None,
        "rating_pct": num(act.get("rating"), d.get("rating"), cast=int),
        "votes": votes,
        "vis_stars": vis_stars,
        "vis_votes": vis_votes,
        "diff_num": diff_num,
        "diff_num_top": num(d.get("difficulty"), cast=int),
        "act_mtb": d.get("act_mtb"),
        "activitytypes": d.get("activitytypes"),
        "connector": d.get("connector"),
        "closed": d.get("closed"),
        "hidden": d.get("hidden"),
        "unsanctioned": d.get("unsanctioned"),
        "archived": d.get("archived"),
        "planned": d.get("planned"),
        "trailtype": d.get("trailtype"),
        "direction": d.get("direction"),
        "distance_m": num(d.get("distance")),
        "created": created,
        "country": d.get("country_name"),
        "prov": d.get("prov_title"),
        "prov_abv": d.get("prov_abv"),
        "city": d.get("city_title"),
        "region_name": d.get("region_name"),
        "ridingarea": d.get("ridingarea_name"),
        "line": [[round(a, 5), round(b, 5)] for a, b in line],
        "description": d.get("seo_description"),
    }


def parse_cards_file(path: str):
    html = Path(path).read_text(errors="replace")
    out = []
    if "trail-card" not in html:
        return out
    for part in re.split(r'(?=<div class="grid-card trail-card)', html):
        m_id = re.search(r'data-trailid="(\d+)"', part)
        if not m_id:
            continue
        g = lambda p: (re.search(p, part) or [None, None])[1]
        m_name = re.search(r'href="(https://www\.trailforks\.com/trails/[a-z0-9-]+/)"[^>]*class="[^"]*bold[^"]*"[^>]*>([^<]+)', part) or re.search(r'href="(https://www\.trailforks\.com/trails/[a-z0-9-]+/)"[^>]*>([^<]+)', part)
        m_star = re.search(r'title="Rating"><span[^>]*>\s*&#9733;\s*</span>\s*([0-9.]+)', part)
        m_diff = re.search(r'class="dicon_small\s+([^"]+)"\s+title="([^"]+)"', part)
        m_loc = re.search(r'<div class="margin-bottom-10 margin-top-5 grey">([^<]+)</div>', part)
        try:
            lat = float(g(r'data-lat="([^"]+)"'))
            lon = float(g(r'data-lng="([^"]+)"'))
        except (TypeError, ValueError):
            lat = lon = None
        dn = g(r'data-difficulty="(\d+)"')
        out.append({
            "trailforks_id": m_id.group(1),
            "name": m_name.group(2).strip() if m_name else None,
            "url": m_name.group(1) if m_name else None,
            "lat": lat, "lon": lon,
            "stars": float(m_star.group(1)) if m_star else None,
            "diff_num": int(dn) if dn else None,
            "diff_title": m_diff.group(2) if m_diff else None,
            "location": re.sub(r"\s+", " ", m_loc.group(1)).strip() if m_loc else None,
            "file": Path(path).name,
        })
    return out


def parse_region_file(path: str):
    html = Path(path).read_text(errors="replace")
    slug = re.sub(r"_p\d+\.html$", "", Path(path).name)
    out = []
    for r in re.findall(r"<tr[\s\S]*?</tr>", html):
        m_id = re.search(r"item-nid' data-nid='(\d+)'", r) or re.search(r'data-id="(\d+)"', r)
        m_url = re.search(r'href="(https://www\.trailforks\.com/trails/[a-z0-9-]+/)"[^>]*>([^<]+)', r)
        if not (m_id and m_url):
            continue
        m_votes = re.search(r'title="([0-9.]+)\s*/\s*5 with (\d+) votes?"', r)
        m_diff = re.search(r'class="dicon_small\s+([^"]+)"\s+title="([^"]+)"', r)
        m_ds = re.search(r'data-sort="(\d+)" class="dicon_small', r)
        m_area = re.search(r'href="https://www\.trailforks\.com/region/([a-z0-9-]+)/">([^<]+)</a>', r)
        out.append({
            "trailforks_id": m_id.group(1),
            "name": m_url.group(2).strip(),
            "url": m_url.group(1),
            "votes": int(m_votes.group(2)) if m_votes else 0,
            "table_stars": float(m_votes.group(1)) if m_votes else None,
            "diff_title": m_diff.group(2) if m_diff else None,
            "diff_sort": int(m_ds.group(1)) if m_ds else None,
            "closed": "closed_trail" in r,
            "area": m_area.group(2) if m_area else None,
            "state_slug": slug,
        })
    return out


def main():
    det_files = sorted(glob.glob(str(CACHE / "details" / "*.html")))
    with Pool(8) as p:
        details = p.map(parse_detail_file, det_files, chunksize=20)
    (CACHE / "v2_details.json").write_text(json.dumps(details))
    print("details", len(details), Counter("error" in d for d in details))

    card_files = sorted(glob.glob(str(CACHE / "lists" / "*.html"))) + sorted(
        str(p) for p in CACHE.glob("*.html"))
    cards = {}
    for f in card_files:
        for c in parse_cards_file(f):
            prev = cards.get(c["trailforks_id"])
            if not prev or (c["stars"] or 0) > (prev["stars"] or 0):
                cards[c["trailforks_id"]] = c
    (CACHE / "v2_cards.json").write_text(json.dumps(list(cards.values())))
    print("cards", len(cards))

    reg_files = sorted(glob.glob(str(CACHE / "regions" / "*.html")))
    with Pool(8) as p:
        res = p.map(parse_region_file, reg_files, chunksize=10)
    rows = {}
    for lst in res:
        for r in lst:
            prev = rows.get(r["trailforks_id"])
            if not prev or r["votes"] > prev["votes"]:
                rows[r["trailforks_id"]] = r
    (CACHE / "v2_region_rows.json").write_text(json.dumps(list(rows.values())))
    print("region rows", len(rows))


if __name__ == "__main__":
    main()
