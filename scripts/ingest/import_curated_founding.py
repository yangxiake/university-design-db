#!/usr/bin/env python3
"""Import AI-curated founding year drafts only when an official excerpt backs them."""

import csv
import pathlib

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["name_zh"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/official-excerpts-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    decisions = yaml.safe_load((ROOT / "data/review/founding-decisions-2026.yaml").read_text(encoding="utf-8"))
    created = added = skipped = 0
    for decision in decisions:
        name = decision["name_zh"]
        year = decision["year"]
        row = scope[name]
        folder = ROOT / "universities" / row["province"] / row["school_code"]
        path = folder / "profile.yaml"
        is_new = not path.exists()
        profile = (profile_for(row) if is_new else yaml.safe_load(path.read_text(encoding="utf-8")))
        fact = profile["culture"]["founded_year"]
        if profile["research"]["status"] == "reviewed" or fact["availability"] != "unresearched":
            skipped += 1
            continue
        matches = [item for item in evidence if item["school_code"] == row["school_code"]
                   and item["field_hint"] == "founded_year"
                   and item["candidate_year"] == str(year)
                   and item["status"] == "candidate"]
        if not matches:
            raise ValueError("Missing direct official excerpt for %s %s" % (name, year))
        source = matches[0]
        fact.update(value=year, source=source["source_url"], basis=decision["basis"],
                    verified="auto", checked_at=source["checked_at"],
                    availability="found", search_sources=[])
        profile["research"].update(status="auto_collected", checked_at=source["checked_at"])
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")
        (folder / "OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        created += int(is_new)
        added += 1
    print("Added %d founding-year drafts (%d new profiles), skipped %d existing values." %
          (added, created, skipped))


if __name__ == "__main__":
    main()
