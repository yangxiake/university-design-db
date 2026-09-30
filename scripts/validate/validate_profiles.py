#!/usr/bin/env python3
"""Validate 933 profiles, field provenance, and optional release readiness."""

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys
from urllib.parse import urlparse

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ingest"))
from render_official import render as render_official  # noqa: E402
SCOPE = ROOT / "data/universities-scope-2026.csv"
FIELDS = {
    "identity": {"name_en", "official_website"},
    "visual": {"color_primary", "color_secondary", "vi_url", "badge_description"},
    "culture": {"founded_year", "motto", "flower", "mascot", "anthem"},
    "resources": {"official_templates_url", "official_template_publisher", "official_template_terms"},
}
RESEARCH_STATUS = {"unresearched", "in_progress", "needs_review", "reviewed"}
AVAILABILITY = {"unresearched", "found", "not_found", "conflict"}
VERIFICATION = {"unverified", "auto", "human"}
URL_VALUE_FIELDS = {"official_website", "vi_url", "official_templates_url"}
COLOR_FIELDS = {"color_primary", "color_secondary"}


def is_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username


def is_date(value):
    if isinstance(value, dt.datetime):
        return False
    if isinstance(value, dt.date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = dt.date.fromisoformat(value)
        except ValueError:
            return False
    else:
        return False
    return parsed <= dt.date.today()


def check_fact(fact, key, label, errors, release=False):
    required = {"value", "source", "verified", "checked_at", "availability", "search_sources"}
    if not isinstance(fact, dict) or not required <= set(fact):
        errors.append(label + ": missing fact metadata")
        return False
    value = fact["value"]
    availability = fact["availability"]
    if availability not in AVAILABILITY:
        errors.append(label + ": invalid availability")
        return False
    if fact["verified"] not in VERIFICATION:
        errors.append(label + ": invalid verified status")
    search_sources = fact["search_sources"]
    if not isinstance(search_sources, list) or any(not is_url(url) for url in search_sources):
        errors.append(label + ": search_sources must contain only webpage URLs")
        search_sources = []

    if availability == "unresearched":
        if value is not None or fact["source"] is not None or fact["checked_at"] is not None:
            errors.append(label + ": unresearched fact must be empty")
        if fact["verified"] != "unverified" or search_sources:
            errors.append(label + ": unresearched fact cannot be verified or have search sources")
        return False
    if not is_date(fact["checked_at"]):
        errors.append(label + ": checked_at must be a nonfuture YYYY-MM-DD")
    if availability == "not_found":
        if value is not None or fact["source"] is not None:
            errors.append(label + ": not_found must not assert a value")
        if not search_sources:
            errors.append(label + ": not_found requires a search log URL")
        if fact["verified"] == "unverified":
            errors.append(label + ": researched absence needs an extraction status")
        if release and fact["verified"] != "human":
            errors.append(label + ": not_found requires human review for release")
        return False
    if availability == "conflict":
        candidates = fact.get("candidates")
        if value is not None or fact["source"] is not None:
            errors.append(label + ": conflict must not choose a value")
        if not isinstance(candidates, list) or len(candidates) < 2:
            errors.append(label + ": conflict needs at least two sourced candidates")
        elif any(not isinstance(item, dict) or not item.get("value") or not is_url(item.get("source"))
                 for item in candidates):
            errors.append(label + ": each conflict candidate needs value and webpage URL")
        if fact["verified"] == "unverified":
            errors.append(label + ": conflict needs an extraction status")
        if release:
            errors.append(label + ": unresolved conflict blocks release")
        return False

    # A found field is a positive assertion and needs a direct source.
    if value is None or value == "":
        errors.append(label + ": found status requires a nonempty value")
    if not is_url(fact["source"]):
        errors.append(label + ": found value requires a webpage source URL")
    if fact["verified"] == "unverified":
        errors.append(label + ": found value needs an extraction status")
    if release and fact["verified"] != "human":
        errors.append(label + ": release requires human verification")
    if key in URL_VALUE_FIELDS and not is_url(value):
        errors.append(label + ": value must be a webpage URL")
    elif key in COLOR_FIELDS:
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            errors.append(label + ": color value must be six-digit HEX")
        if fact.get("method") not in {"official_vi", "badge_sample", "manual_derived"}:
            errors.append(label + ": color method required")
    elif key == "founded_year":
        if type(value) is not int or not 1000 <= value <= dt.date.today().year:
            errors.append(label + ": founded_year must be a plausible integer")
        if not isinstance(fact.get("basis"), str) or not fact["basis"].strip():
            errors.append(label + ": founded_year requires a stated historical basis")
    elif key not in URL_VALUE_FIELDS:
        if not isinstance(value, str) or len(value) > 500:
            errors.append(label + ": value must be short text (max 500 characters)")
    return True


def check_list(items, key, label, errors, release=False):
    cap = 5 if key == "history_events" else 3
    if not isinstance(items, list) or len(items) > cap:
        errors.append(label + ": must be a list of at most %d entries" % cap)
        return 0
    for number, item in enumerate(items):
        entry = "%s[%d]" % (label, number)
        if not isinstance(item, dict):
            errors.append(entry + ": must be an object")
            continue
        if key == "history_events":
            if type(item.get("year")) is not int or not 1000 <= item["year"] <= dt.date.today().year:
                errors.append(entry + ": invalid year")
            if not isinstance(item.get("event"), str) or not 0 < len(item["event"]) <= 200:
                errors.append(entry + ": event must be short text")
        elif not isinstance(item.get("name"), str) or not 0 < len(item["name"]) <= 100:
            errors.append(entry + ": landmark name must be short text")
        if not is_url(item.get("source")):
            errors.append(entry + ": source webpage URL required")
        if not is_date(item.get("checked_at")):
            errors.append(entry + ": checked_at YYYY-MM-DD required")
        if item.get("verified") not in VERIFICATION:
            errors.append(entry + ": invalid verified status")
        elif release and item["verified"] != "human":
            errors.append(entry + ": release requires human verification")
    return len(items)


def validate_profile(path, row, release=False):
    errors = []
    try:
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [str(path) + ": " + str(exc)], 0, False
    if not isinstance(profile, dict) or profile.get("schema_version") != 2:
        return [str(path) + ": schema_version must be 2"], 0, False
    identity = profile.get("identity")
    if not isinstance(identity, dict):
        return [str(path) + ": identity object missing"], 0, False
    for column in ("school_code", "name_zh", "province", "city", "level", "authority", "note"):
        if identity.get(column) != row[column]:
            errors.append(str(path) + ": identity.%s differs from 2026 scope" % column)
    if identity.get("registry_source") != row["source_url"]:
        errors.append(str(path) + ": registry source differs from 2026 scope")
    expected_path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
    if path != expected_path:
        errors.append(str(path) + ": path must use province and school code")
    classification = profile.get("classification")
    if not isinstance(classification, dict):
        errors.append(str(path) + ": classification object missing")
    elif (classification.get("scope_category") != row["scope_category"]
          or classification.get("scope_tags") != row["scope_tags"].split("|")
          or classification.get("scope_source") != (row["scope_source_url"] or None)):
        errors.append(str(path) + ": classification differs from 2026 scope")
    research = profile.get("research")
    if not isinstance(research, dict) or research.get("status") not in RESEARCH_STATUS:
        errors.append(str(path) + ": invalid research status")
        research = {}
    if research.get("status") == "reviewed":
        if not is_date(research.get("checked_at")) or not research.get("reviewed_by"):
            errors.append(str(path) + ": reviewed profile needs date and reviewer")
    elif research.get("status") in {"in_progress", "needs_review"}:
        if not is_date(research.get("checked_at")):
            errors.append(str(path) + ": researched profile needs a valid date")
    elif research.get("reviewed_by"):
        errors.append(str(path) + ": reviewer set before review completion")
    if release and research.get("status") != "reviewed":
        errors.append(str(path) + ": human review incomplete")

    populated = 0
    groups = {}
    for group, fields in FIELDS.items():
        value = profile.get(group)
        if not isinstance(value, dict) or not fields <= set(value):
            errors.append(str(path) + ": missing %s fields" % group)
            continue
        groups[group] = value
        for key in fields:
            populated += int(check_fact(value[key], key, str(path) + "." + group + "." + key,
                                        errors, release))
    if "visual" in groups:
        populated += check_list(groups["visual"].get("landmarks"), "landmarks",
                                str(path) + ".visual.landmarks", errors, release)
    if "culture" in groups:
        populated += check_list(groups["culture"].get("history_events"), "history_events",
                                str(path) + ".culture.history_events", errors, release)
    if research.get("status") == "unresearched" and populated:
        errors.append(str(path) + ": populated facts contradict unresearched status")
    if release and all(group in groups for group in ("visual", "culture", "resources")):
        for group, key in (("visual", "color_primary"), ("culture", "founded_year"),
                           ("resources", "official_templates_url")):
            if groups[group][key].get("availability") == "unresearched":
                errors.append(str(path) + ": release requires research of %s" % key)
    ready = (all(group in groups for group in ("visual", "culture"))
             and groups["visual"]["color_primary"].get("availability") == "found"
             and groups["culture"]["founded_year"].get("availability") == "found"
             and groups["visual"]["color_primary"].get("verified") == "human"
             and groups["culture"]["founded_year"].get("verified") == "human")
    return errors, populated, ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Require human review of all published facts")
    args = parser.parse_args()
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 933 or len({r["school_code"] for r in rows}) != 933:
        raise SystemExit("Scope is not 933 unique school codes")
    by_code = {r["school_code"]: r for r in rows}
    paths = sorted((ROOT / "universities").glob("*/*/profile.yaml"))
    errors = []
    if args.release and len(paths) != 933:
        errors.append("Release requires 933 profile.yaml files, found %d" % len(paths))
    found_codes = set()
    populated = ready_count = 0
    for path in paths:
        code = path.parent.name
        if code in found_codes or code not in by_code:
            errors.append(str(path) + ": duplicate or out-of-scope school code")
            continue
        found_codes.add(code)
        found, count, ready = validate_profile(path, by_code[code], args.release)
        errors.extend(found)
        populated += count
        ready_count += int(ready)
        official = path.parent / "OFFICIAL.md"
        if not official.exists():
            errors.append(str(path.parent) + ": OFFICIAL.md missing")
        else:
            profile = yaml.safe_load(path.read_text(encoding="utf-8"))
            if official.read_text(encoding="utf-8") != render_official(profile):
                errors.append(str(official) + ": generated resource view is stale")
    if args.release and found_codes != set(by_code):
        errors.append("Missing profile codes: " + ",".join(sorted(set(by_code) - found_codes)[:10]))
    print("Profiles: %d; found facts: %d; human color+year ready: %d; errors: %d" %
          (len(paths), populated, ready_count, len(errors)))
    for error in errors[:100]:
        print("ERROR:", error)
    if len(errors) > 100:
        print("... %d further errors" % (len(errors) - 100))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
