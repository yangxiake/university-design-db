#!/usr/bin/env python3
"""Validate 1412 profiles, field provenance, and optional release readiness."""

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
from profile_extensions import FACTS as EXTENDED_FACTS, COLLECTIONS, rgb  # noqa: E402
SCOPE = ROOT / "data/universities-scope-2026.csv"
FIELDS = {
    "identity": {"name_en", "official_website"},
    "visual": {"color_primary", "color_secondary", "vi_url", "badge_description"},
    "culture": {"founded_year", "motto", "flower", "mascot", "anthem"},
    "resources": {"official_templates_url", "official_template_publisher", "official_template_terms"},
}
RESEARCH_STATUS = {"unresearched", "in_progress", "auto_collected", "needs_review", "reviewed"}
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


def check_fact(fact, key, label, errors, release=False, value_type=None):
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
    if fact.get('source_type')=='community_dataset':
        if not re.fullmatch(r'[0-9a-f]{40}',str(fact.get('upstream_commit',''))):
            errors.append(label+': community fact needs upstream commit')
        for metadata in ('upstream_repository','upstream_record_name','upstream_license','source_as_of'):
            if not fact.get(metadata):
                errors.append(label+': community fact missing '+metadata)
    if value_type == 'text_list':
        if not isinstance(value, list) or not value or any(not isinstance(item,str) or not item.strip() or len(item)>200 for item in value):
            errors.append(label+': value must be a nonempty short-text list')
    elif value_type == 'coordinates':
        if not isinstance(value,dict):
            errors.append(label+': coordinates must be an object')
        else:
            for field, limit in [('latitude',90),('longitude',180)]:
                item=value.get(field)
                if type(item) not in {int,float} or not -limit<=item<=limit:
                    errors.append(label+': invalid '+field)
            if value.get('crs') not in {'WGS84','GCJ02','BD09','unspecified'} or not value.get('precision') or not value.get('location_kind'):
                errors.append(label+': coordinates need declared system, precision and location kind')
    elif value_type == 'number':
        import math
        if type(value) not in {int,float} or not math.isfinite(value) or value<0:
            errors.append(label+': value must be a nonnegative finite number')
        if not fact.get('source_as_of') or not fact.get('basis'):
            errors.append(label+': statistics need a date and counting basis')
    elif (key in URL_VALUE_FIELDS or value_type == 'url') and not is_url(value):
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
    if not isinstance(profile, dict) or profile.get("schema_version") not in {2,3}:
        return [str(path) + ": schema_version must be 2 or 3"], 0, False
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
    elif research.get("status") in {"in_progress", "needs_review", "auto_collected"}:
        if not is_date(research.get("checked_at")):
            errors.append(str(path) + ": researched profile needs a valid date")
    elif research.get("reviewed_by"):
        errors.append(str(path) + ": reviewer set before review completion")
    candidates=research.get('website_candidates',[])
    if not isinstance(candidates,list):
        errors.append(str(path)+': website_candidates must be a list')
        candidates=[]
    if candidates and not is_date(research.get('website_candidates_updated_at')):
        errors.append(str(path)+': website candidate sync date required')
    for candidate in candidates:
        if not isinstance(candidate,dict) or not is_url(candidate.get('url')) or not is_url(candidate.get('source')) or candidate.get('status')!='unverified_candidate':
            errors.append(str(path)+': website candidate needs URLs and unverified_candidate status')
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
    if profile.get('schema_version') == 3:
        for dotted, (value_type, description) in EXTENDED_FACTS.items():
            group,key=dotted.split('.')
            populated += int(check_fact(profile.get(group,{}).get(key),key,str(path)+'.'+dotted,
                                        errors,release,value_type=value_type))
        for dotted in COLLECTIONS:
            group,key=dotted.split('.')
            items=profile.get(group,{}).get(key)
            if not isinstance(items,list):
                errors.append(str(path)+': '+dotted+' must be a list')
                continue
            for index,item in enumerate(items):
                check_extended_entry(dotted,item,str(path)+'.'+dotted+'[%d]'%index,errors,release)
    resources = profile.get('resources', {}).get('community_resources', [])
    if not isinstance(resources, list):
        errors.append(str(path)+': community_resources must be a list')
        resources=[]
    urls=set()
    for entry in resources:
        if not isinstance(entry, dict):
            errors.append(str(path)+': community resource must be an object')
            continue
        for field in ('title','publisher','kind','usage_note'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(str(path)+': community resource missing '+field)
        if entry.get('official') is not False:
            errors.append(str(path)+': community resource cannot be marked official')
        if not is_url(entry.get('url')) or not is_url(entry.get('source')):
            errors.append(str(path)+': community resource needs entry and source URLs')
        if entry.get('url') in urls:
            errors.append(str(path)+': duplicate community resource')
        urls.add(entry.get('url'))
        if not re.fullmatch(r'[0-9a-f]{40}',str(entry.get('commit',''))):
            errors.append(str(path)+': community resource needs pinned commit')
        if release and entry.get('verified')!='human':
            errors.append(str(path)+': audited community resource requires human verification')
        if entry.get('verified') not in {'auto','human'} or not is_date(entry.get('checked_at')):
            errors.append(str(path)+': community resource needs verification status and date')
        if entry.get('license') is not None and not isinstance(entry['license'],str):
            errors.append(str(path)+': invalid community resource license')
        for color in entry.get('palette',[]):
            if not isinstance(color,dict) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',str(color.get('value',''))) or color.get('method')!='community_theme' or not color.get('basis'):
                errors.append(str(path)+': invalid community palette or missing basis')
    if resources and research.get('status')=='unresearched':
        errors.append(str(path)+': community resources contradict unresearched status')
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


def check_extended_entry(dotted, item, label, errors, release=False):
    if not isinstance(item,dict):
        errors.append(label+': collection entry must be an object')
        return
    if not is_url(item.get('source')) or not is_date(item.get('checked_at')) or item.get('verified') not in {'auto','human'}:
        errors.append(label+': source URL, date and extraction status required')
    if release and item.get('verified')!='human':
        errors.append(label+': release requires human verification')
    commit=item.get('commit') or item.get('upstream_commit')
    if commit is not None and not re.fullmatch(r'[0-9a-f]{40}',str(commit)):
        errors.append(label+': invalid pinned commit')
    if dotted=='visual.logo_assets':
        for key in ('asset_id','kind','title','publisher','rights_holder','usage_note'):
            if not isinstance(item.get(key),str) or not item[key]:
                errors.append(label+': missing '+key)
        if not is_url(item.get('url')) or item.get('kind') not in {'badge','wordmark','combination','anniversary','site_identity'}:
            errors.append(label+': logo needs a concrete URL and asset kind')
        if item.get('repository') and (item.get('official') is not False or not commit):
            errors.append(label+': community logo must stay nonofficial and pinned')
        if item.get('access_status') not in {'indexed_not_fetched','content_inspected','inspection_failed'}:
            errors.append(label+': invalid asset access status')
        if item.get('access_status')=='content_inspected':
            if not re.fullmatch('[0-9a-f]{64}',str(item.get('sha256',''))) or not item.get('byte_size'):
                errors.append(label+': inspected asset needs content hash and byte size')
        for key in ('width','height'):
            if item.get(key) is not None and (type(item[key]) not in {int,float} or item[key]<=0):
                errors.append(label+': invalid '+key)
        if item.get('asset_license') is not None and not isinstance(item['asset_license'],str):
            errors.append(label+': invalid asset license')
    elif dotted=='visual.color_palette':
        value=item.get('value')
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}',str(value)):
            errors.append(label+': six-digit HEX required')
        elif item.get('rgb')!=rgb(value):
            errors.append(label+': RGB does not match HEX')
        method=item.get('method')
        if method not in {'official_vi','badge_sample','manual_derived','community_theme','community_logo_sample'}:
            errors.append(label+': invalid color method')
        if item.get('official') is not (method=='official_vi'):
            errors.append(label+': official flag must follow color evidence method')
        if not item.get('basis') or item.get('role') not in {'primary','secondary','reference','accent'}:
            errors.append(label+': color role and extraction basis required')
    elif dotted=='visual.vi_resources':
        if not is_url(item.get('url')) or not isinstance(item.get('formats'),list) or not item.get('access_requirement'):
            errors.append(label+': VI resource needs URL, formats and access requirement')
        if item.get('repository') and item.get('official') is not False:
            errors.append(label+': a community directory is not an official publisher')
    elif dotted=='rankings.entries':
        if type(item.get('year')) is not int or not 1900<=item['year']<=dt.date.today().year:
            errors.append(label+': ranking edition year required')
        if not item.get('publisher') or not item.get('ranking_name') or not item.get('scope'):
            errors.append(label+': ranking publisher, name and scope required')
        if type(item.get('rank')) is not int or item['rank']<=0:
            errors.append(label+': rank must be a positive integer')
    elif dotted=='academics.subject_assessments':
        if not item.get('subject') or not item.get('publisher') or type(item.get('round')) is not int or not item.get('completeness'):
            errors.append(label+': assessment subject, publisher, round and selection basis required')
        if item.get('availability','found')=='conflict':
            candidates=item.get('candidates',[])
            if item.get('grade') is not None or len(candidates)<2 or any(c.get('grade') not in {'A+','A','A-','B+','B','B-','C+','C','C-'} or not is_url(c.get('source')) for c in candidates):
                errors.append(label+': assessment conflict must preserve sourced grades without choosing')
        elif item.get('grade') not in {'A+','A','A-','B+','B','B-','C+','C','C-'}:
            errors.append(label+': invalid assessment grade')
    elif dotted.startswith('admissions.'):
        if type(item.get('year')) is not int or not 1900<=item['year']<=dt.date.today().year:
            errors.append(label+': admission year required')
        for key in ('region','curriculum','batch','enrollment_type'):
            if not item.get(key):errors.append(label+': admission missing '+key)
        for key in ('minimum_score','minimum_rank','enrolled_count','tuition','duration_years','planned_count'):
            if item.get(key) is not None and (type(item[key]) not in {int,float} or item[key]<0):
                errors.append(label+': invalid admission '+key)
    elif dotted=='community.snapshots':
        target=item.get('data_path')
        if not isinstance(target,str) or not target.startswith('data/external/') or '..' in pathlib.PurePosixPath(target).parts or not (ROOT/target).is_file():
            errors.append(label+': snapshot must reference a local licensed data subset')
        if not item.get('license') or not item.get('data_as_of') or not isinstance(item.get('upstream_fields'),list):
            errors.append(label+': snapshot license, date and field list required')
    elif dotted=='identity.external_identifiers':
        if not item.get('namespace') or not item.get('value'):
            errors.append(label+': external identifier needs namespace and value')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Optional audited-edition gate: require human review")
    parser.add_argument("--automatic-draft", action="store_true", help="Require all scope identities and valid sourced metadata, without human sign-off")
    args = parser.parse_args()
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1412 or len({r["school_code"] for r in rows}) != 1412:
        raise SystemExit("Scope is not 1412 unique school codes")
    by_code = {r["school_code"]: r for r in rows}
    paths = sorted((ROOT / "universities").glob("*/*/profile.yaml"))
    errors = []
    if (args.release or args.automatic_draft) and len(paths) != len(rows):
        errors.append("Release requires 1412 profile.yaml files, found %d" % len(paths))
    found_codes = set()
    populated = ready_count = 0
    for path in paths:
        code = path.parent.name
        if args.automatic_draft and yaml.safe_load(path.read_text()).get('schema_version')!=3:
            errors.append(str(path)+': automatic edition requires schema_version 3')
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
    if (args.release or args.automatic_draft) and found_codes != set(by_code):
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
