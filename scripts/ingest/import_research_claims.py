#!/usr/bin/env python3
"""Import strict official claims, keeping unresolved research visible.

All assertions remain AI drafts. The research ledger is linked separately from
fact provenance, and a page visit is never promoted to completed school research.
"""

import collections
import csv
import json
import pathlib
import re

import yaml

from render_official import render
from seed_profiles import profile_for

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data/review/school-research-2026.jsonl"


def normalized(field, value):
    if isinstance(value, int):
        return value
    if field == "culture.motto":
        return re.sub(r"[\s，,、；;·]", "", value)
    if field == "identity.name_en":
        return re.sub(r"\s+", " ", value).strip().lower()
    return value


def choose_claims(field, choices):
    by_value = {}
    for item in choices:
        by_value.setdefault(normalized(field, item["value"]), item)
    if field == "visual.vi_url":
        # Several valid pages are alternative entry links, not contradictory values.
        return [min(choices, key=lambda item: len(item["value"]))]
    return list(by_value.values())


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()]
    added = created = conflicts = retained = 0
    differences = []
    for school in rows:
        code = school["school_code"]
        row = scope[code]
        if school["name_zh"] != row["name_zh"]:
            raise ValueError("Scope identity mismatch")
        folder = ROOT / "universities" / row["province"] / code
        path = folder / "profile.yaml"
        # Do not create an empty profile for a school with no confirmed source or visit.
        if not path.exists() and not school["home"] and not school["claims"]:
            continue
        is_new = not path.exists()
        profile = profile_for(row) if is_new else yaml.safe_load(path.read_text(encoding="utf-8"))
        if profile["research"]["status"] == "reviewed":
            retained += 1
            continue
        by_field = collections.defaultdict(list)
        for claim in school["claims"]:
            by_field[claim["field"]].append(claim)
        for field, candidates in by_field.items():
            choices = choose_claims(field, candidates)
            group, key = field.split(".")
            fact = profile[group][key]
            if field=='identity.name_en' and fact.get('source_type')=='community_dataset' and fact.get('verified')=='auto':
                # A direct school source takes priority over an older community dataset.
                old=dict(fact)
                for choice in choices:
                    if normalized(field,old['value'])!=normalized(field,choice['value']):
                        differences.append(dict(school_code=code,name_zh=row['name_zh'],field=field,
                                                existing_value=old['value'],existing_source=old['source'],
                                                candidate_value=choice['value'],candidate_source=choice['source'],
                                                checked_at=school['checked_at']))
                for extra in ('source_type','upstream_repository','upstream_commit','upstream_record_name','upstream_license','source_as_of','note'):
                    fact.pop(extra,None)
                fact.update(value=None,source=None,availability='unresearched',verified='unverified',checked_at=None,search_sources=[])
            if fact["availability"] != "unresearched":
                retained += 1
                if fact["availability"] == "conflict" and fact["verified"] == "auto":
                    seen = {normalized(field, c["value"]) for c in fact["candidates"]}
                    for candidate in choices:
                        value = normalized(field, candidate["value"])
                        if value not in seen:
                            fact["candidates"].append({k: v for k, v in candidate.items() if k != "field"})
                            seen.add(value)
                            fact["checked_at"] = school["checked_at"]
                if fact["availability"] == "found" and key != "vi_url":
                    for candidate in choices:
                        if normalized(field, fact["value"]) != normalized(field, candidate["value"]):
                            differences.append(dict(school_code=code, name_zh=row["name_zh"], field=field,
                                                    existing_value=fact["value"], existing_source=fact["source"],
                                                    candidate_value=candidate["value"], candidate_source=candidate["source"],
                                                    checked_at=school["checked_at"]))
                    divergent = [c for c in choices if normalized(field, fact["value"]) != normalized(field, c["value"])]
                    if divergent and fact["verified"] == "auto":
                        existing_choice = {"value": fact["value"], "source": fact["source"]}
                        if fact.get("basis"):
                            existing_choice["basis"] = fact["basis"]
                        fact.update(value=None, source=None, availability="conflict", verified="auto",
                                    checked_at=school["checked_at"], search_sources=[],
                                    candidates=[existing_choice] + [{k: v for k, v in c.items() if k != "field"} for c in divergent],
                                    note="已存AI草稿与本轮官网候选不一致；两者均保留，等待核对原页和历史口径")
                        fact.pop("basis", None)
                        conflicts += 1
                continue
            if len(choices) > 1:
                fact.update(value=None, source=None, availability="conflict", verified="auto",
                            checked_at=school["checked_at"], search_sources=[],
                            candidates=[{k: v for k, v in claim.items() if k != "field"} for claim in choices],
                            note="已访问官网页面给出不同候选；需核对名称、标点或历史口径")
                conflicts += 1
            else:
                choice = choices[0]
                fact.update(value=choice["value"], source=choice["source"], availability="found", verified="auto",
                            checked_at=school["checked_at"], search_sources=[])
                if choice.get("basis"):
                    fact["basis"] = choice["basis"]
                added += 1
        profile["research"].update(status="auto_collected", checked_at=school["checked_at"],
                                   collection_status=school["status"],
                                   audit_ledger="data/review/school-research-2026.jsonl",
                                   audit_key=code)
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        path.with_name("OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        created += int(is_new)
    output = ROOT / "data/review/research-claim-differences-2026.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["school_code", "name_zh", "field", "existing_value",
                                                   "existing_source", "candidate_value", "candidate_source", "checked_at"])
        writer.writeheader()
        writer.writerows(differences)
    print(f"Imported {added} explicit facts; created {created} researched profiles; "
          f"{conflicts} new conflicts; {len(differences)} differences for review; {retained} existing facts retained.")


if __name__ == "__main__":
    main()
