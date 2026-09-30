#!/usr/bin/env python3
"""Join scope and candidate leads into a school-by-school human review queue."""

import csv
import pathlib

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]


def read_by_code(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["school_code"]: row for row in csv.DictReader(handle)}


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    candidates = read_by_code(ROOT / "data/review/wikidata-candidates-2026.csv")
    gaps = read_by_code(ROOT / "data/review/wikidata-search-gaps-2026.csv")
    if len(candidates) != 933 or set(candidates) != {r["school_code"] for r in scope}:
        raise ValueError("Candidate set does not match 2026 scope")
    rows = []
    for school in scope:
        code = school["school_code"]
        candidate = candidates[code]
        gap = gaps.get(code, {})
        path = pathlib.Path("universities") / school["province"] / code / "profile.yaml"
        exists = (ROOT / path).exists()
        status = (yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))["research"]["status"]
                  if exists else "unresearched")
        rows.append({
            "priority": 1 if "double_first" in school["scope_tags"].split("|") else 2,
            "school_code": code,
            "name_zh": school["name_zh"],
            "province": school["province"],
            "scope_category": school["scope_category"],
            "research_status": status,
            "profile_path": path.as_posix() if exists else "",
            "candidate_match_status": candidate["match_status"],
            "candidate_websites_unverified": candidate["candidate_websites"],
            "candidate_years_unverified": candidate["candidate_inception_years"],
            "candidate_wikidata_items_unverified": candidate["wikidata_items"],
            "additional_search_status": gap.get("status", ""),
            "additional_search_ids_unverified": gap.get("candidate_ids", ""),
            "next_step": "人工核对已有档案来源" if status == "needs_review" else
                         "查官方来源并建立档案" if status == "unresearched" else
                         "继续核查资料" if status == "in_progress" else "定期复核",
        })
    rows.sort(key=lambda item: (item["priority"], item["province"], item["school_code"]))
    output = ROOT / "data/review/review-queue-2026.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote %d review tasks: %d first-priority Double First Class." % (
        len(rows), sum(row["priority"] == 1 for row in rows)))


if __name__ == "__main__":
    main()
