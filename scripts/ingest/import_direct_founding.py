#!/usr/bin/env python3
"""Import only direct school-founding assertions from official overview pages.

This narrow pattern is still an automated reading, so facts stay verified:auto.
Merged institutions and earlier predecessors can use different founding dates;
the stored basis names the school's own wording rather than resolving history.
"""

import collections
import csv
import pathlib
import re

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]


def direct_claim(row):
    pattern = re.compile(
        r"(?:^|[。；;])\s*(?:" + re.escape(row["name_zh"]) +
        r"|学校)\s*(始建|创建|创办|建校)于?\s*(\d{4})年")
    match = pattern.search(row["excerpt"])
    if match and match.group(2) == row["candidate_year"]:
        return match.group(1), int(match.group(2))
    return None


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        discovery = {row["school_code"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/official-excerpts-2026.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        excerpts = list(csv.DictReader(handle))
    candidates = collections.defaultdict(list)
    for excerpt in excerpts:
        code = excerpt["school_code"]
        if excerpt["status"] != "candidate" or excerpt["field_hint"] != "founded_year":
            continue
        if discovery[code]["status"] != "title_matched" or not discovery[code]["overview_url"]:
            continue
        claim = direct_claim(excerpt)
        if claim:
            candidates[code].append((claim, excerpt))
    added = ambiguous = existing = 0
    for code, choices in candidates.items():
        years = {claim[1] for claim, _ in choices}
        if len(years) != 1:
            ambiguous += 1
            continue
        (verb, year), source = choices[0]
        school = scope[code]
        folder = ROOT / "universities" / school["province"] / code
        path = folder / "profile.yaml"
        profile = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists()
                   else profile_for(school))
        fact = profile["culture"]["founded_year"]
        if profile["research"]["status"] == "reviewed" or fact["availability"] != "unresearched":
            existing += 1
            continue
        fact.update(value=year, source=source["source_url"],
                    basis=f"官网学校简介将{year}年记为学校{verb}年份",
                    verified="auto", checked_at=source["checked_at"],
                    availability="found", search_sources=[])
        profile["research"].update(status="needs_review", checked_at=source["checked_at"])
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")
        (folder / "OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        added += 1
    print("Added %d directly stated founding years; %d ambiguous, %d existing skipped." %
          (added, ambiguous, existing))


if __name__ == "__main__":
    main()
