#!/usr/bin/env python3
"""Import selected official facts for previously unprofiled priority schools.

Each fact has its own direct school source. Entries are AI research drafts and
cannot satisfy the release gate without a separate human review.
"""

import csv
import datetime as dt
import pathlib

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "data/review/priority-official-facts-2026.yaml"
FIELDS = {
    "official_website": ("identity", "official_website"),
    "vi_url": ("visual", "vi_url"),
    "badge_description": ("visual", "badge_description"),
    "anthem": ("culture", "anthem"),
    "mascot": ("culture", "mascot"),
    "official_templates_url": ("resources", "official_templates_url"),
    "official_template_publisher": ("resources", "official_template_publisher"),
    "official_template_terms": ("resources", "official_template_terms"),
    "motto": ("culture", "motto"),
    "founded_year": ("culture", "founded_year"),
}


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    decisions = yaml.safe_load(DECISIONS.read_text(encoding="utf-8"))
    if len({item["school_code"] for item in decisions}) != len(decisions):
        raise ValueError("Duplicate school decision")
    today = dt.date.today().isoformat()
    added = existing = created = 0
    for item in decisions:
        school = scope[item["school_code"]]
        if "double_first" not in school["scope_tags"].split("|"):
            raise ValueError("Not a priority school: " + school["name_zh"])
        if item["name_zh"] != school["name_zh"]:
            raise ValueError("School identity mismatch: " + item["school_code"])
        path = ROOT / "universities" / school["province"] / school["school_code"] / "profile.yaml"
        is_new = not path.exists()
        profile = profile_for(school) if is_new else yaml.safe_load(path.read_text(encoding="utf-8"))
        if profile["research"]["status"] == "reviewed":
            existing += 1
            continue
        changed = False
        for key, spec in item["facts"].items():
            group, field = FIELDS[key]
            if spec.get("availability") == "not_found":
                fact = profile[group][field]
                if fact["availability"] == "unresearched":
                    fact.update(value=None, source=None, verified="auto", checked_at=today,
                                availability="not_found", search_sources=spec["search_sources"],
                                note=spec["note"])
                    added += 1
                    changed = True
                elif fact["availability"] == "not_found":
                    existing += 1
                else:
                    raise ValueError("Existing fact differs: " + school["name_zh"] + " " + key)
                continue
            if not spec.get("source") or not spec.get("value"):
                raise ValueError("Fact needs source/value: " + school["name_zh"] + " " + key)
            fact = profile[group][field]
            if fact["availability"] != "unresearched":
                if fact["availability"] != "found" or fact["value"] != spec["value"]:
                    raise ValueError("Existing fact differs: " + school["name_zh"] + " " + key)
                existing += 1
                continue
            fact.update(value=spec["value"], source=spec["source"], verified="auto",
                        checked_at=today, availability="found", search_sources=[])
            if key == "founded_year":
                fact["basis"] = spec["basis"]
            added += 1
            changed = True
        if changed:
            profile["research"].update(status="needs_review", checked_at=today)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                            encoding="utf-8")
            path.with_name("OFFICIAL.md").write_text(render(profile), encoding="utf-8")
            created += is_new
    print("Added %d source-linked priority facts; %d new profiles; %d existing facts kept." %
          (added, created, existing))


if __name__ == "__main__":
    main()
