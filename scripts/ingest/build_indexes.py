#!/usr/bin/env python3
"""Build browse indexes from the canonical 1412-school scope and profiles."""

import collections
import argparse
import csv
import io
import pathlib

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data/universities-scope-2026.csv"
OUT = ROOT / "indexes"


def write(name, fields, rows, check=False):
    OUT.mkdir(exist_ok=True)
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    expected = handle.getvalue().encode("utf-8-sig")
    path = OUT / name
    if check:
        if not path.exists() or path.read_bytes() != expected:
            raise ValueError("Derived index is stale: " + str(path))
    else:
        path.write_bytes(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check existing indexes without changing them")
    args = parser.parse_args()
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        scope = list(csv.DictReader(handle))
    if len(scope) != 1412:
        raise ValueError("Scope must contain exactly 1412 schools")
    catalog = []
    province_count = collections.Counter()
    category_count = collections.Counter()
    tag_count = collections.Counter()
    status_count = collections.Counter()
    resource_index = []
    for row in scope:
        profile_path = pathlib.Path("universities") / row["province"] / row["school_code"] / "profile.yaml"
        absolute = ROOT / profile_path
        if absolute.exists():
            profile = yaml.safe_load(absolute.read_text(encoding="utf-8"))
            if profile["identity"]["school_code"] != row["school_code"]:
                raise ValueError("Profile mismatch: " + row["school_code"])
            research_status = profile["research"]["status"]
            color_status = profile["visual"]["color_primary"]["availability"]
            year_status = profile["culture"]["founded_year"]["availability"]
            template_status = profile["resources"]["official_templates_url"]["availability"]
            entries = profile["resources"].get("community_resources", [])
            for entry in entries:
                resource_index.append(dict(school_code=row['school_code'], name_zh=row['name_zh'],
                                           kind=entry['kind'],title=entry['title'],url=entry['url'],
                                           license=entry.get('license') or '',commit=entry['commit'],
                                           source=entry['source'],profile_path=profile_path.as_posix()))
        else:
            research_status = color_status = year_status = template_status = "unresearched"
            entries = []
        tags = row["scope_tags"].split("|")
        catalog.append({
            "school_code": row["school_code"],
            "name_zh": row["name_zh"],
            "province": row["province"],
            "city": row["city"],
            "level": row["level"],
            "scope_category": row["scope_category"],
            "scope_tags": row["scope_tags"],
            "research_status": research_status,
            "color_status": color_status,
            "founded_year_status": year_status,
            "template_status": template_status,
            "community_resource_count": len(entries),
            "community_path": (profile_path.parent / "COMMUNITY.md").as_posix() if entries else "",
            "profile_path": profile_path.as_posix() if absolute.exists() else "",
        })
        province_count[row["province"]] += 1
        category_count[row["scope_category"]] += 1
        status_count[research_status] += 1
        tag_count.update(tags)
    write("catalog.csv", list(catalog[0]), catalog, args.check)
    write("community-resources.csv", ["school_code","name_zh","kind","title","url","license","commit","source","profile_path"], resource_index, args.check)
    for filename, label, counts in (
        ("by-province.csv", "province", province_count),
        ("by-category.csv", "scope_category", category_count),
        ("by-tag.csv", "scope_tag", tag_count),
        ("by-status.csv", "research_status", status_count),
    ):
        write(filename, [label, "count"], [{label: key, "count": value}
                                            for key, value in sorted(counts.items())], args.check)
    print(("Checked" if args.check else "Built"), "catalog, resource and four classification indexes for 1412 schools.")


if __name__ == "__main__":
    main()
