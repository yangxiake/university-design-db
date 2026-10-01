#!/usr/bin/env python3
"""Small regression checks for source, scope, and human release gates."""

import csv
import pathlib
import sys
import tempfile
import unittest
from urllib.parse import urlparse

import yaml

from validate_profiles import check_fact, validate_profile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ingest"))
from discover_official_pages import save_results


class DataRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.scope = list(csv.DictReader(handle))

    def test_scope_has_no_military_and_unique_codes(self):
        self.assertEqual(len(self.scope), 1412)
        self.assertEqual(len({r["school_code"] for r in self.scope}), 1412)
        self.assertFalse({"国防科技大学", "海军军医大学", "空军军医大学"}
                         & {r["name_zh"] for r in self.scope})
        with (ROOT / "universities-index.csv").open(encoding="utf-8-sig", newline="") as handle:
            official = {r["school_code"] for r in csv.DictReader(handle) if r["level"] == "本科"}
        self.assertEqual({r["school_code"] for r in self.scope}, official)
        self.assertEqual(sum("vocational_undergraduate" in r["scope_tags"].split("|")
                             for r in self.scope), 124)

    def test_positive_fact_requires_source(self):
        errors = []
        check_fact({"value": "#660874", "source": None, "verified": "auto",
                    "checked_at": "2026-09-30", "availability": "found",
                    "search_sources": [], "method": "official_vi"},
                   "color_primary", "test", errors)
        self.assertTrue(any("source URL" in item for item in errors))

    def test_partial_discovery_resume_keeps_other_schools(self):
        scope = [{"school_code": "first"}, {"school_code": "other"}]
        results = {"other": {"school_code": "other", "status": "fetch_error"}}
        results["first"] = {"school_code": "first", "status": "title_matched"}
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "discovery.csv"
            save_results(output, scope, results)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual([row["school_code"] for row in rows], ["first", "other"])
        self.assertEqual(rows[1]["status"], "fetch_error")

    def test_auto_example_cannot_pass_release(self):
        row = next(r for r in self.scope if r["name_zh"] == "清华大学")
        path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
        errors, _, _ = validate_profile(path, row, release=True)
        self.assertTrue(any("human review incomplete" in item for item in errors))
        self.assertTrue(any("release requires human verification" in item for item in errors))
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(profile["research"]["status"], "auto_collected")

    def test_review_queue_covers_scope_without_asserting_candidates(self):
        with (ROOT / "data/review/review-queue-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
            queue = list(csv.DictReader(handle))
        self.assertEqual({r["school_code"] for r in queue},
                         {r["school_code"] for r in self.scope})
        self.assertEqual(sum(r["priority"] == "1" for r in queue), 144)
        actual_profiles = list((ROOT / "universities").glob("*/*/profile.yaml"))
        self.assertEqual(sum(bool(r["profile_path"]) for r in queue), len(actual_profiles))
        reviewed_state = sum(yaml.safe_load(path.read_text(encoding="utf-8"))["research"]["status"]
                             == "auto_collected" for path in actual_profiles)
        self.assertEqual(sum(r["research_status"] == "auto_collected" for r in queue), reviewed_state)

    def test_matched_sites_are_unique_and_third_party_leads_stay_out(self):
        with (ROOT / "data/review/official-page-discovery-2026.csv").open(
                encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({r["school_code"] for r in rows},
                         {r["school_code"] for r in self.scope})
        matched = [r for r in rows if r["status"] == "title_matched"]
        hosts = [urlparse(r["homepage_url"]).hostname for r in matched]
        # Independent colleges can use a distinct path on their parent's domain.
        endpoints = [r["homepage_url"].rstrip("/") for r in matched]
        self.assertEqual(len(endpoints), len(set(endpoints)))
        from discover_official_pages import matches_school_title
        names = [r["name_zh"] for r in self.scope]
        for item in matched:
            self.assertTrue(matches_school_title(item["name_zh"],item["homepage_title"],names))
        self.assertNotIn("www.at0086.com", hosts)
        for path in (ROOT / "universities").glob("*/*/profile.yaml"):
            profile = yaml.safe_load(path.read_text(encoding="utf-8"))
            website = profile["identity"]["official_website"]
            if website["availability"] == "found":
                self.assertNotEqual(urlparse(website["value"]).hostname, "www.at0086.com")


if __name__ == "__main__":
    unittest.main()
