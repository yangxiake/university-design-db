#!/usr/bin/env python3
"""Import source-linked official color decisions as AI drafts, never human facts."""

import csv
import datetime as dt
import pathlib
import re

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "data/review/official-color-decisions-2026.yaml"


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    decisions = yaml.safe_load(DECISIONS.read_text(encoding="utf-8"))
    if len({item["school_code"] for item in decisions}) != len(decisions):
        raise ValueError("Duplicate school in official color decisions")
    added = existing = 0
    today = dt.date.today().isoformat()
    for decision in decisions:
        school = scope[decision["school_code"]]
        if decision["name_zh"] != school["name_zh"]:
            raise ValueError("School code/name mismatch: " + decision["school_code"])
        folder = ROOT / "universities" / school["province"] / school["school_code"]
        path = folder / "profile.yaml"
        profile = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists()
                   else profile_for(school))
        if profile["research"]["status"] == "reviewed":
            existing += 1
            continue
        changed = False
        absence = decision.get("color_primary_not_found")
        if absence:
            if decision.get("color_primary") or decision.get("color_primary_conflict"):
                raise ValueError("Primary color absence cannot also assert a color")
            fact = profile["visual"]["color_primary"]
            if fact["availability"] == "unresearched":
                fact.update(value=None, source=None, verified="auto", checked_at=today,
                            availability="not_found", search_sources=absence["search_sources"],
                            note=absence["note"])
                added += 1
                changed = True
            elif fact["availability"] == "not_found":
                existing += 1
            else:
                raise ValueError("Existing color differs: " + school["name_zh"])
        conflict = decision.get("color_primary_conflict")
        if conflict:
            if decision.get("color_primary"):
                raise ValueError("Primary color cannot be both found and conflicted: " + school["name_zh"])
            candidates = []
            for candidate in conflict["candidates"]:
                if not re.fullmatch(r"#[0-9A-F]{6}", candidate["value"]):
                    raise ValueError("Bad conflict HEX: " + school["name_zh"])
                candidates.append({"value": candidate["value"], "source": decision["source"],
                                   "basis": candidate["basis"]})
            if len({candidate["value"] for candidate in candidates}) < 2:
                raise ValueError("Conflict must have distinct values: " + school["name_zh"])
            fact = profile["visual"]["color_primary"]
            if fact["availability"] == "unresearched":
                fact.update(value=None, source=None, verified="auto", checked_at=today,
                            availability="conflict", search_sources=[], candidates=candidates,
                            label=conflict["label"], note=conflict["reason"])
                added += 1
                changed = True
            elif fact["availability"] == "conflict" and fact.get("candidates") == candidates:
                existing += 1
            else:
                raise ValueError("Existing color differs: " + school["name_zh"] + " color_primary")
        for key in ("color_primary", "color_secondary"):
            spec = decision.get(key)
            if not spec:
                continue
            if not re.fullmatch(r"#[0-9A-F]{6}", spec["value"]):
                raise ValueError("Bad six-digit HEX: " + school["name_zh"])
            fact = profile["visual"][key]
            if fact["availability"] != "unresearched":
                if fact["availability"] != "found" or fact["value"] != spec["value"]:
                    raise ValueError("Existing color differs: " + school["name_zh"] + " " + key)
                existing += 1
                continue
            fact.update(value=spec["value"], source=spec.get("source", decision["source"]),
                        method="official_vi", label=spec["label"], basis=spec["basis"],
                        verified="auto", checked_at=today, availability="found", search_sources=[])
            if spec.get("role_note"):
                fact["role_note"] = spec["role_note"]
            added += 1
            changed = True
        if decision.get("vi_url"):
            fact = profile["visual"]["vi_url"]
            if fact["availability"] == "unresearched":
                fact.update(value=decision["vi_url"], source=decision["source"],
                            verified="auto", checked_at=today, availability="found",
                            search_sources=[])
                added += 1
                changed = True
        if changed:
            profile["research"].update(status="auto_collected", checked_at=today)
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                            encoding="utf-8")
            (folder / "OFFICIAL.md").write_text(render(profile), encoding="utf-8")
    print("Added %d color/VI facts from official sources; %d existing values kept." %
          (added, existing))


if __name__ == "__main__":
    main()
