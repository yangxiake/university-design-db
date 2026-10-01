#!/usr/bin/env python3
"""Create empty, source-identified profiles for the complete 1412-school scope.

This never overwrites a profile. Empty profiles are preparation for research,
not evidence of completed research or publication readiness.
"""

import argparse
import csv
import pathlib

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data/universities-scope-2026.csv"


def empty_fact():
    return {
        "value": None,
        "source": None,
        "verified": "unverified",
        "checked_at": None,
        "availability": "unresearched",
        "search_sources": [],
    }


def profile_for(row):
    from profile_extensions import migrate
    return migrate({
        "schema_version": 2,
        "identity": {
            "school_code": row["school_code"],
            "name_zh": row["name_zh"],
            "province": row["province"],
            "city": row["city"],
            "level": row["level"],
            "authority": row["authority"],
            "note": row["note"],
            "registry_source": row["source_url"],
            "name_en": empty_fact(),
            "official_website": empty_fact(),
        },
        "classification": {
            "scope_category": row["scope_category"],
            "scope_tags": row["scope_tags"].split("|"),
            "scope_source": row["scope_source_url"] or None,
        },
        "research": {"status": "unresearched", "checked_at": None, "reviewed_by": None},
        "visual": {
            "color_primary": empty_fact(),
            "color_secondary": empty_fact(),
            "vi_url": empty_fact(),
            "badge_description": empty_fact(),
            "landmarks": [],
        },
        "culture": {
            "founded_year": empty_fact(),
            "motto": empty_fact(),
            "history_events": [],
            "flower": empty_fact(),
            "mascot": empty_fact(),
            "anthem": empty_fact(),
        },
        "resources": {
            "official_templates_url": empty_fact(),
            "official_template_publisher": empty_fact(),
            "official_template_terms": empty_fact(),
        },
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--school-code", help="Create one empty draft for research")
    selection.add_argument("--all", action="store_true", help="Explicitly create drafts for all 1412 schools")
    args = parser.parse_args()
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1412 or len({r["school_code"] for r in rows}) != 1412:
        raise ValueError("Scope must contain 1412 unique Ministry school codes")
    created = 0
    for row in rows:
        if args.school_code and row["school_code"] != args.school_code:
            continue
        folder = ROOT / "universities" / row["province"] / row["school_code"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "profile.yaml"
        if path.exists():
            continue
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(profile_for(row), handle, allow_unicode=True, sort_keys=False, width=100)
        from render_official import render
        (folder / "OFFICIAL.md").write_text(render(profile_for(row)), encoding="utf-8")
        created += 1
    if args.school_code and not any(row["school_code"] == args.school_code for row in rows):
        raise ValueError("School code is not in 2026 scope")
    print("Created %d empty drafts; 1412 identities in scope." % created)


if __name__ == "__main__":
    main()
