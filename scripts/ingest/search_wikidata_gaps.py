#!/usr/bin/env python3
"""Search Wikidata for names with no safe unique exact-label match.

Results are candidate IDs only. A search hit is never a verified school match.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import pathlib
import time
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[2]
API = "https://www.wikidata.org/w/api.php"


def search(row):
    parameters = {"action": "wbsearchentities", "search": row["name_zh"],
                  "language": "zh", "format": "json", "limit": 5}
    url = API + "?" + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, headers={
        "User-Agent": "UniversityDesignDB/0.1 (research leads; github.com/yangxiake)"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            hits = json.load(response).get("search", [])
        return {"school_code": row["school_code"], "name_zh": row["name_zh"],
                "prior_status": row["match_status"],
                "candidate_ids": "|".join(item["id"] for item in hits),
                "candidate_labels": "|".join(item.get("label", "") for item in hits),
                "status": "search_results" if hits else "no_search_results",
                "collected_at": dt.date.today().isoformat(), "query_url": url}
    except Exception as exc:
        return {"school_code": row["school_code"], "name_zh": row["name_zh"],
                "prior_status": row["match_status"], "candidate_ids": "", "candidate_labels": "",
                "status": "request_error:" + type(exc).__name__,
                "collected_at": dt.date.today().isoformat(), "query_url": url}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-errors", action="store_true", help="Retry only failed searches from the output CSV")
    args = parser.parse_args()
    with (ROOT / "data/review/wikidata-candidates-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle)
                if row["match_status"] in {"no_exact_match", "exact_ambiguous"}]
    output = ROOT / "data/review/wikidata-search-gaps-2026.csv"
    if args.retry_errors and output.exists():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            previous = {row["school_code"]: row for row in csv.DictReader(handle)}
        results = []
        for row in rows:
            old = previous.get(row["school_code"])
            if old and not old["status"].startswith("request_error"):
                results.append(old)
                continue
            time.sleep(0.6)
            results.append(search(row))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(search, rows))
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print("Wrote %d gap searches, %d returned candidates, %d request errors." % (
        len(results), sum(r["status"] == "search_results" for r in results),
        sum(r["status"].startswith("request_error") for r in results)))


if __name__ == "__main__":
    main()
