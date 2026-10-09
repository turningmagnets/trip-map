#!/usr/bin/env python3
"""Normalize + validate Trailforks browser-crawl results for build_trails_dataset.py.

Reads   crawl/results/batch_NNN.csv   (combined batches only; batch_NNNa/b/c/d chunk files are ignored)
Writes  cache/trailforks/v3_browser_crawl.json   normalized rows the build merges in
        data/crawl_merge_report.json             counts + problems
        data/crawl_needs_recheck.csv             rows held back (bad rating / no coords / unknown difficulty)

Rules (nothing invented):
  * "none" / "" -> None. A field that is None never overwrites cached data.
  * avg_rating must be a Trailforks page (Bayesian) figure. The page rating is
    ~ (6*3.98 + votes*raw)/(6+votes); a value outside the range that formula allows for
    raw in [1,5] (e.g. 3.0 with 1 vote) is a misread (raw avg / ride-log "Avg") ->
    rating dropped, row flagged for recapture.
  * difficulty wording is mapped to the dataset's Trailforks bands; unknown wording -> None + flag.
  * trailhead outside lat 24..61 / lon -170..-50 -> coords dropped + flag.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/workspace/mtb-trails-map")
RESULTS = ROOT / "crawl" / "results"
QUEUE = ROOT / "crawl" / "queue.csv"
OUT_JSON = ROOT / "cache" / "trailforks" / "v3_browser_crawl.json"
REPORT = ROOT / "data" / "crawl_merge_report.json"
RECHECK = ROOT / "data" / "crawl_needs_recheck.csv"

PRIOR_N, PRIOR_MEAN, TOL = 6, 3.98, 0.10

DIFF_WORDS = [  # checked in order; lowercase substring -> dataset band (same codes as TF_DIFF)
    ("double black", "doubleBlack"), ("extremely difficult", "doubleBlack"), ("dbl", "doubleBlack"),
    ("pro line", "proline"), ("proline", "proline"), ("pro-line", "proline"),
    ("black", "black"), ("very difficult", "black"),
    ("blue", "blue"), ("intermediate", "blue"),
    ("green", "green"), ("easy", "green"),
    ("white", "white"), ("easiest", "white"),
    ("access", "access"),
]


def nz(v):
    v = (v or "").strip()
    return None if v.lower() in ("", "none", "null", "n/a", "-") else v


def map_diff(s):
    s = (s or "").lower()
    for k, band in DIFF_WORDS:
        if k in s:
            return band
    return None


def bayes_range(votes):
    lo = (PRIOR_N * PRIOR_MEAN + votes * 1.0) / (PRIOR_N + votes)
    hi = (PRIOR_N * PRIOR_MEAN + votes * 5.0) / (PRIOR_N + votes)
    return lo - TOL, hi + TOL


def main():
    files = sorted(p for p in RESULTS.glob("batch_*.csv") if re.fullmatch(r"batch_\d{3}\.csv", p.name))
    queue = {r["trailforks_id"]: (i, r) for i, r in enumerate(csv.DictReader(QUEUE.open()))}
    rows, flags, cnt = {}, [], Counter()
    for f in files:
        for r in csv.DictReader(f.open(newline="", encoding="utf-8")):
            cnt["rows_read"] += 1
            tid = nz(r.get("trailforks_id"))
            if not tid or not tid.isdigit():
                cnt["bad_id"] += 1
                flags.append({"batch": f.stem, "trailforks_id": tid, "name": r.get("name"), "problem": "bad trailforks_id"})
                continue
            probs = []
            votes = nz(r.get("votes"))
            votes = int(float(votes)) if votes and re.fullmatch(r"\d+(\.0+)?", votes) else None
            stars = nz(r.get("avg_rating"))
            try:
                stars = float(stars) if stars is not None else None
            except ValueError:
                probs.append(f"unparseable rating {stars!r}")
                stars = None
            if stars is not None and votes is not None:
                lo, hi = bayes_range(votes)
                if not (lo <= stars <= hi):
                    probs.append(f"rating {stars} impossible for page rating with {votes} vote(s) "
                                 f"(allowed {lo + TOL:.2f}-{hi - TOL:.2f}); likely raw/ride-log avg")
                    stars = None
            elif stars is not None and not (1 <= stars <= 5):
                probs.append(f"rating {stars} out of 1-5")
                stars = None
            if stars is None and not probs:
                probs.append("no rating")
            draw = nz(r.get("difficulty"))
            band = map_diff(draw) if draw else None
            if draw and not band:
                probs.append(f"unknown difficulty wording {draw!r}")

            def coord(a, b):
                try:
                    la, lo_ = float(nz(r.get(a))), float(nz(r.get(b)))
                except (TypeError, ValueError):
                    return None, None
                if not (24 <= la <= 61 and -170 <= lo_ <= -50):
                    probs.append(f"{a}/{b} outside US/BC/AB box ({la},{lo_})")
                    return None, None
                return la, lo_
            th_lat, th_lon = coord("trailhead_lat", "trailhead_lon")
            end_lat, end_lon = coord("end_lat", "end_lon")
            if th_lat is None:
                probs.append("no trailhead coords")
            closed = nz(r.get("closed"))
            closed = {"yes": True, "true": True, "closed": True, "1": True,
                      "no": False, "false": False, "open": False, "0": False}.get((closed or "").lower())
            qi, qr = queue.get(tid, (None, {}))
            if qr and band and qr.get("difficulty") and qr["difficulty"] != band:
                cnt["difficulty_changed_vs_queue"] += 1
            if qr and votes is not None and str(votes) != str(qr.get("votes")):
                cnt["votes_changed_vs_queue"] += 1
            rec = {"trailforks_id": tid, "name": nz(r.get("name")), "stars": stars, "votes": votes,
                   "difficulty_raw": draw, "band": band, "riding_area": nz(r.get("riding_area")),
                   "th_lat": th_lat, "th_lon": th_lon, "end_lat": end_lat, "end_lon": end_lon,
                   "closed": closed, "url": nz(r.get("url")), "batch": f.stem,
                   "queue_row": qi, "queue_state": qr.get("state"), "problems": probs}
            if tid in rows:
                cnt["duplicate_id_later_batch_wins"] += 1
            rows[tid] = rec
            for p in probs:
                flags.append({"batch": f.stem, "trailforks_id": tid, "name": rec["name"], "problem": p,
                              "url": rec["url"]})
    usable = [x for x in rows.values() if x["stars"] is not None and x["th_lat"] is not None]
    cnt.update({
        "files": len(files), "unique_trails": len(rows),
        "usable_rating_and_coords": len(usable),
        "usable_ge_3.8": sum(1 for x in usable if x["stars"] >= 3.8),
        "held_no_coords": sum(1 for x in rows.values() if x["th_lat"] is None),
        "held_bad_or_missing_rating": sum(1 for x in rows.values() if x["stars"] is None),
        "held_no_coords_but_rated_ge_3.8": sum(1 for x in rows.values() if x["th_lat"] is None and (x["stars"] or 0) >= 3.8),
    })
    OUT_JSON.write_text(json.dumps(list(rows.values()), indent=1))
    rep = {"files": [p.name for p in files], "counts": dict(cnt),
           "difficulty_raw": dict(Counter(x["difficulty_raw"] for x in rows.values())),
           "problems": dict(Counter(re.sub(r"[\d.]+|\(.*?\)|'.*?'", "#", p["problem"]) for p in flags))}
    REPORT.write_text(json.dumps(rep, indent=2))
    with RECHECK.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["batch", "trailforks_id", "name", "problem", "url"])
        w.writeheader()
        w.writerows(flags)
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
