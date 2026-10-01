#!/usr/bin/env python3
"""Merge a completed follow-up ledger, replacing claims from re-read pages."""
import argparse
import csv
import json
import pathlib

from research_all_schools import ROOT, OUTPUT, FACTS


def merge(base, followup, discovery):
    reread = {p.get("source_url", p["requested_url"]) for p in followup.get("pages", []) if p["status"] == "read"}
    old = [c for c in base.get("claims", []) if c["source"] not in reread]
    claims = old + followup.get("claims", [])
    unique = {json.dumps(c, ensure_ascii=False, sort_keys=True): c for c in claims}
    base["claims"] = list(unique.values())
    visits = base.get("pages", []) + followup.get("pages", [])
    # Retain each visit, including failed attempts followed by success.
    unique_visits = {json.dumps(p, ensure_ascii=False, sort_keys=True): p for p in visits}
    base["pages"] = list(unique_visits.values())
    if discovery.get("status") == "title_matched":
        base["home"] = discovery["homepage_url"]
    base["collector_revision"] = 2
    base["checked_at"] = max(base["checked_at"], followup.get("checked_at", base["checked_at"]))
    good = any(p["status"] == "read" for p in base["pages"])
    base["status"] = ("researched_partial" if good or base["claims"] else
                      "access_limited" if base.get("home") else "needs_source")
    base["field_audit"] = {field: ("explicit_candidate" if any(c["field"] == field for c in base["claims"]) else
                                  "no_explicit_claim_in_visited_pages" if good else
                                  "access_limited" if base.get("home") else "source_not_confirmed") for field in FACTS}
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--followup", type=pathlib.Path,
                        default=ROOT / "data/review/school-research-deeper-2026.jsonl")
    deeper = parser.parse_args().followup
    followups = {r["school_code"]: r for r in (json.loads(l) for l in deeper.read_text().splitlines())}
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig") as handle:
        codes = {r["school_code"] for r in csv.DictReader(handle)}
    if set(followups) != codes:
        raise ValueError("Follow-up pass must cover all scope rows before merging")
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(encoding="utf-8-sig") as handle:
        discovery = {r["school_code"]: r for r in csv.DictReader(handle)}
    rows = [json.loads(l) for l in OUTPUT.read_text().splitlines()]
    if {r["school_code"] for r in rows} != codes:
        raise ValueError("Base ledger scope mismatch")
    merged = [merge(r, followups[r["school_code"]], discovery.get(r["school_code"], {})) for r in rows]
    temp = OUTPUT.with_suffix(".jsonl.tmp")
    temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Merged {len(merged)} schools; {sum(len(r['pages']) for r in merged)} visits; "
          f"{sum(len(r['claims']) for r in merged)} explicit candidates.")


if __name__ == "__main__":
    main()
