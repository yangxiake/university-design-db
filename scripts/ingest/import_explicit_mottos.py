#!/usr/bin/env python3
"""Import a single explicitly quoted motto from school-linked official excerpts.

Conflicting or unquoted candidates stay in the review data. All imported
values remain verified:auto until a human checks the original page.
"""

import collections
import csv
import pathlib
import re

import yaml

from render_official import render
from seed_profiles import profile_for


ROOT = pathlib.Path(__file__).resolve().parents[2]
PATTERNS = [
    re.compile(r"“([^”]{2,32})”(?:的)?校训"),
    re.compile(r"以“([^”]{2,32})”为校训"),
    re.compile(r"校训(?:是|为|：|:)?“([^”]{2,32})”"),
    re.compile(r"校训“([^”]{2,32})”"),
]


def candidate_values(sentence):
    return {match.group(1).strip() for pattern in PATTERNS for match in pattern.finditer(sentence)}


def main():
    with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        scope = {row["school_code"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/review/official-excerpts-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
        excerpts = list(csv.DictReader(handle))
    by_school = collections.defaultdict(list)
    for excerpt in excerpts:
        if excerpt["status"] == "candidate" and excerpt["field_hint"] == "motto":
            for value in candidate_values(excerpt["excerpt"]):
                by_school[excerpt["school_code"]].append((value, excerpt))
    created = added = ambiguous = skipped = 0
    for code, choices in by_school.items():
        values = {value for value, _ in choices}
        if len(values) != 1:
            ambiguous += 1
            continue
        value = next(iter(values))
        source = next(excerpt for choice, excerpt in choices if choice == value)
        row = scope[code]
        folder = ROOT / "universities" / row["province"] / code
        path = folder / "profile.yaml"
        is_new = not path.exists()
        profile = profile_for(row) if is_new else yaml.safe_load(path.read_text(encoding="utf-8"))
        fact = profile["culture"]["motto"]
        if profile["research"]["status"] == "reviewed" or fact["availability"] != "unresearched":
            skipped += 1
            continue
        fact.update(value=value, source=source["source_url"], verified="auto",
                    checked_at=source["checked_at"], availability="found", search_sources=[])
        profile["research"].update(status="auto_collected", checked_at=source["checked_at"])
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")
        (folder / "OFFICIAL.md").write_text(render(profile), encoding="utf-8")
        created += int(is_new)
        added += 1
    print("Added %d explicit mottos (%d new profiles); %d ambiguous, %d existing skipped." %
          (added, created, ambiguous, skipped))


if __name__ == "__main__":
    main()
