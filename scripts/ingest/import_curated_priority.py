#!/usr/bin/env python3
"""Import selected official facts for previously unprofiled priority schools.

Each fact has its own direct school source. Entries are AI research drafts and
cannot satisfy the release gate without a separate human review.
"""

import argparse
import csv
import datetime as dt
import pathlib

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "data/review/priority-official-facts-2026.yaml"
FIELDS = {
    "name_en": ("identity", "name_en"),
    "official_website": ("identity", "official_website"),
    "vi_url": ("visual", "vi_url"),
    "badge_description": ("visual", "badge_description"),
    "anthem": ("culture", "anthem"),
    "mascot": ("culture", "mascot"),
    "flower": ("culture", "flower"),
    "official_templates_url": ("resources", "official_templates_url"),
    "official_template_publisher": ("resources", "official_template_publisher"),
    "official_template_terms": ("resources", "official_template_terms"),
    "motto": ("culture", "motto"),
    "founded_year": ("culture", "founded_year"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, default=DECISIONS)
    parser.add_argument("--all-scope", action="store_true", help="Allow any school in the frozen 1412-school scope")
    parser.add_argument("--keep-existing", action="store_true", help="Fill gaps only; retain existing scalar facts and conflicts")
    args = parser.parse_args()
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    decisions = yaml.safe_load(args.input.read_text(encoding="utf-8"))
    if len({item["school_code"] for item in decisions}) != len(decisions):
        raise ValueError("Duplicate school decision")
    today = dt.date.today().isoformat()
    added = existing = created = 0
    for item in decisions:
        school = scope[item["school_code"]]
        if not args.all_scope and "double_first" not in school["scope_tags"].split("|"):
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
            if key in {"history_events", "landmarks"}:
                group = "culture" if key == "history_events" else "visual"
                if profile[group][key]:
                    existing += len(profile[group][key])
                    continue
                cap = 5 if key == "history_events" else 3
                if not isinstance(spec, list) or len(spec) > cap:
                    raise ValueError("Invalid list: " + key)
                for entry in spec:
                    if not entry.get("source"):
                        raise ValueError("Missing entry source: " + key)
                profile[group][key] = [{**entry, "verified": "auto", "checked_at": today} for entry in spec]
                added += len(spec)
                changed = True
                continue
            group, field = FIELDS[key]
            if args.keep_existing and profile[group][field]["availability"] != "unresearched":
                existing += 1
                continue
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
            if spec.get("availability") == "conflict":
                candidates = spec.get("candidates", [])
                if len({str(c.get("value")) for c in candidates}) < 2 or any(
                        not c.get("value") or not c.get("source") for c in candidates):
                    raise ValueError("Conflict needs distinct sourced values: " + key)
                fact = profile[group][field]
                if fact["availability"] != "unresearched":
                    raise ValueError("Existing fact differs: " + school["name_zh"] + " " + key)
                fact.update(value=None, source=None, verified="auto", checked_at=today,
                            availability="conflict", search_sources=[], candidates=candidates,
                            note=spec["note"])
                added += 1
                changed = True
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
            if spec.get("note"):
                fact["note"] = spec["note"]
            added += 1
            changed = True
        if changed:
            profile["research"].update(status="auto_collected", checked_at=today)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                            encoding="utf-8")
            path.with_name("OFFICIAL.md").write_text(render(profile), encoding="utf-8")
            created += is_new
    print("Added %d source-linked curated facts; %d new profiles; %d existing facts kept." %
          (added, created, existing))


if __name__ == "__main__":
    main()
