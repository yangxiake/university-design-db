"""Viewer bundles must remain lossless derived views, with no copied graphic assets."""
import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from build_viewer import build, catalog_row


class ViewerDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / 'indexes/ppt-profiles.jsonl').read_bytes()
        cls.records = [json.loads(line) for line in cls.raw.decode('utf-8').splitlines()]

    def test_regional_records_equal_ppt_source(self):
        catalog = json.loads((ROOT / 'viewer/data/catalog.json').read_text())
        self.assertEqual(catalog['source_sha256'], hashlib.sha256(self.raw).hexdigest())
        found = {}
        for province in catalog['provinces']:
            bundle = json.loads((ROOT / 'viewer/data/provinces' / (province + '.json')).read_text())
            found.update(bundle['schools'])
        self.assertEqual(found, {r['school_code']: r for r in self.records})

    def test_catalog_search_preserves_identity_and_sourced_names(self):
        row = catalog_row(self.records[0])
        self.assertEqual(row['school_code'], self.records[0]['school_code'])
        fact = self.records[0]['identity']['aliases']
        if fact['availability'] == 'found':
            self.assertTrue(set(fact['value']) <= set(row['search_names']))

    def test_generation_is_deterministic(self):
        self.assertEqual(build(self.records, self.raw), build(self.records, self.raw))

    def test_no_graphics_or_upstream_scripts_in_viewer_data(self):
        self.assertTrue(all(p.suffix == '.json' for p in (ROOT / 'viewer/data').rglob('*') if p.is_file()))


if __name__ == '__main__':
    unittest.main()
