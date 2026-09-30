#!/usr/bin/env python3
"""Small regression checks for source, scope, and human release gates."""

import csv
import pathlib
import unittest

import yaml

from validate_profiles import check_fact, validate_profile


ROOT = pathlib.Path(__file__).resolve().parents[2]


class DataRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/universities-scope-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.scope = list(csv.DictReader(handle))

    def test_scope_has_no_military_and_unique_codes(self):
        self.assertEqual(len(self.scope), 933)
        self.assertEqual(len({r["school_code"] for r in self.scope}), 933)
        self.assertFalse({"国防科技大学", "海军军医大学", "空军军医大学"}
                         & {r["name_zh"] for r in self.scope})

    def test_positive_fact_requires_source(self):
        errors = []
        check_fact({"value": "#660874", "source": None, "verified": "auto",
                    "checked_at": "2026-09-30", "availability": "found",
                    "search_sources": [], "method": "official_vi"},
                   "color_primary", "test", errors)
        self.assertTrue(any("source URL" in item for item in errors))

    def test_auto_example_cannot_pass_release(self):
        row = next(r for r in self.scope if r["name_zh"] == "清华大学")
        path = ROOT / "universities" / row["province"] / row["school_code"] / "profile.yaml"
        errors, _, _ = validate_profile(path, row, release=True)
        self.assertTrue(any("human review incomplete" in item for item in errors))
        self.assertTrue(any("release requires human verification" in item for item in errors))
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(profile["research"]["status"], "needs_review")

    def test_review_queue_covers_scope_without_asserting_candidates(self):
        with (ROOT / "data/review/review-queue-2026.csv").open(encoding="utf-8-sig", newline="") as handle:
            queue = list(csv.DictReader(handle))
        self.assertEqual({r["school_code"] for r in queue},
                         {r["school_code"] for r in self.scope})
        self.assertEqual(sum(r["priority"] == "1" for r in queue), 144)
        self.assertEqual(sum(r["research_status"] == "needs_review" for r in queue), 4)
        self.assertEqual(sum(bool(r["profile_path"]) for r in queue), 4)


if __name__ == "__main__":
    unittest.main()
