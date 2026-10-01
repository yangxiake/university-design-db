#!/usr/bin/env python3
"""Add accessible school-level visual/identity page links to existing profiles.

Only fetched pages whose title explicitly denotes the school's identification
or VI system qualify. Generic campus culture and department pages stay leads.
"""

import csv
import pathlib
import re

import yaml

from render_official import render


ROOT = pathlib.Path(__file__).resolve().parents[2]
TITLE = re.compile(r"标识|识别|VI设计|校徽|校标|校旗")


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/visual-color-leads-2026.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        leads = list(csv.DictReader(handle))
    by_school = {}
    for lead in leads:
        by_school.setdefault(lead["school_code"], lead)
    added = skipped = 0
    for code, lead in by_school.items():
        if lead["status"] not in {"candidate", "no_pattern"} or not TITLE.search(lead["page_title"]):
            continue
        school = scope[code]
        path = ROOT / "universities" / school["province"] / code / "profile.yaml"
        if not path.exists():
            skipped += 1
            continue
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        fact = profile["visual"]["vi_url"]
        if profile["research"]["status"] == "reviewed" or fact["availability"] != "unresearched":
            skipped += 1
            continue
        fact.update(value=lead["source_url"], source=lead["source_url"],
                    verified="auto", checked_at=lead["checked_at"],
                    availability="found", search_sources=[])
        profile["research"].update(status="auto_collected", checked_at=lead["checked_at"])
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")
        path.with_name("OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        added += 1
    print("Added %d school visual/VI entry links; skipped %d existing or missing profiles." %
          (added, skipped))


if __name__ == "__main__":
    main()
