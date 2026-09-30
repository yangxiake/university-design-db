#!/usr/bin/env python3
"""Collect secondary-source leads for review; never mark profile facts verified.

Wikidata coverage and statements vary. This CSV is a work queue, not a
published claim about a school. Only exact Chinese-name matches are joined.
"""

import collections
import csv
import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[2]
ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = '''SELECT DISTINCT ?item ?name ?website ?inception WHERE {
  ?item wdt:P17 wd:Q148 ; wdt:P31/wdt:P279* wd:Q3918 ; rdfs:label ?name .
  FILTER(LANG(?name) = "zh")
  OPTIONAL { ?item wdt:P856 ?website . }
  OPTIONAL { ?item wdt:P571 ?inception . }
} LIMIT 5000'''


def fetch(query):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={
        "User-Agent": "UniversityDesignDB/0.1 (research leads; github.com/yangxiake)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["results"]["bindings"]


def add_bindings(by_name, bindings):
    for item in bindings:
        group = by_name[item["name"]["value"]]
        group["items"].add(item["item"]["value"].replace("http://", "https://"))
        if "website" in item:
            group["websites"].add(item["website"]["value"])
        if "inception" in item:
            group["years"].add(item["inception"]["value"][:4])


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    by_name = collections.defaultdict(lambda: {"items": set(), "websites": set(), "years": set()})
    add_bindings(by_name, fetch(QUERY))
    classed_names = set(by_name)
    unmatched = [r["name_zh"] for r in scope if r["name_zh"] not in by_name]
    for start in range(0, len(unmatched), 50):
        names = unmatched[start:start + 50]
        values = " ".join(json.dumps(name, ensure_ascii=False) + "@zh" for name in names)
        fallback = '''SELECT DISTINCT ?item ?name ?website ?inception WHERE {
          VALUES ?name { %s }
          ?item rdfs:label ?name .
          OPTIONAL { ?item wdt:P856 ?website . }
          OPTIONAL { ?item wdt:P571 ?inception . }
        } LIMIT 5000''' % values
        add_bindings(by_name, fetch(fallback))
    rows = []
    for school in scope:
        group = by_name.get(school["name_zh"])
        if not group:
            status = "no_exact_match"
        elif len(group["items"]) != 1:
            status = "exact_ambiguous"
        elif school["name_zh"] in classed_names:
            status = "exact_unique_classed"
        else:
            status = "exact_unique_label_only"
        rows.append({
            "school_code": school["school_code"],
            "name_zh": school["name_zh"],
            "match_status": status,
            "wikidata_items": "|".join(sorted(group["items"])) if group else "",
            "candidate_websites": "|".join(sorted(group["websites"])) if group else "",
            "candidate_inception_years": "|".join(sorted(group["years"])) if group else "",
            "collected_at": dt.date.today().isoformat(),
            "query_endpoint": ENDPOINT,
        })
    out = ROOT / "data/review/wikidata-candidates-2026.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote %d candidate rows: %d classed, %d label-only, %d ambiguous, %d unmatched." % (
        len(rows),
        sum(r["match_status"] == "exact_unique_classed" for r in rows),
        sum(r["match_status"] == "exact_unique_label_only" for r in rows),
        sum(r["match_status"] == "exact_ambiguous" for r in rows),
        sum(r["match_status"] == "no_exact_match" for r in rows),
    ))


if __name__ == "__main__":
    main()
