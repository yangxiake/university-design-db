#!/usr/bin/env python3
"""Add source-linked homepage fields when a candidate site's title names the school.

This is an automated match, not human verification. Existing researched or
reviewed values are never overwritten.
"""

import csv
import pathlib

import yaml

from render_official import render
from discover_official_pages import matches_school_title
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/official-page-discovery-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        matches = list(csv.DictReader(handle))
    created = added = skipped = 0
    for match in matches:
        if match["status"] != "title_matched" or not match["homepage_url"]:
            continue
        row = scope[match["school_code"]]
        if not matches_school_title(row["name_zh"],match["homepage_title"],[r["name_zh"] for r in scope.values()]):
            continue
        folder = ROOT / "universities" / row["province"] / row["school_code"]
        path = folder / "profile.yaml"
        is_new = not path.exists()
        if not is_new:
            profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            profile = profile_for(row)
        if profile["research"]["status"] == "reviewed":
            skipped += 1
            continue
        fact = profile["identity"]["official_website"]
        if fact["availability"] != "unresearched":
            skipped += 1
            continue
        fact.update(value=match["homepage_url"], source=match["homepage_url"],
                    checked_at=match["checked_at"], verified="auto",
                    availability="found", search_sources=[])
        profile["research"].update(status="auto_collected", checked_at=match["checked_at"])
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")
        (folder / "OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        added += 1
        created += int(is_new)
    print("Added %d automatically matched homepages (%d new profiles); skipped %d existing fields." %
          (added, created, skipped))


if __name__ == "__main__":
    main()
