"""Boundary tests for public PPT exports, source metadata and offline gates."""
import copy
import csv
import io
import json
import pathlib
import sys
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from build_ppt_profiles import assert_scope, check_output, colors_for, csv_row, logos_for, record_for, serialize
from build_ppt_indexes import rows_for
from yaml_io import load_yaml
from validate_profiles import check_extended_entry, check_fact
from validate_schemas import diagnostics, schema_validator


class PPTExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / 'universities/北京市/4111010003/profile.yaml'
        cls.profile = load_yaml(cls.path.read_text(encoding='utf-8'))
        cls.canonical = schema_validator('profile-schema-v4.json')
        cls.export = schema_validator('ppt-export-schema-v1.json')

    def setUp(self):
        self.profile = copy.deepcopy(self.__class__.profile)

    def fact(self, **kwargs):
        return dict(value='#123456', source='https://example.edu/vi', checked_at='2026-10-01',
                    verified='auto', availability='found', search_sources=[], **kwargs)

    def visual(self, primary=None, palette=None, assets=None):
        result = self.profile['visual']
        if primary is not None:
            result['color_primary'] = primary
        result['color_palette'] = palette or []
        result['logo_assets'] = assets or []
        return result

    def test_duplicate_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'school_code: duplicate'):
            assert_scope([{'school_code': '4111010003'}] * 2, [])

    def test_source_less_positive_reports_field(self):
        self.profile['overview']['summary_zh'] = self.fact()
        self.profile['overview']['summary_zh']['source'] = None
        errors = diagnostics(self.canonical, self.profile, '4111010003')
        self.assertTrue(any('4111010003: overview.summary_zh.source:' in e for e in errors))
        semantic = []
        check_fact(self.profile['overview']['summary_zh'], 'summary_zh', '4111010003: overview.summary_zh', semantic)
        self.assertTrue(any('source URL' in e for e in semantic))

    def test_mismatched_rgb_is_rejected(self):
        entry = dict(self.fact(), rgb=[1, 2, 3], method='official_vi', official=True,
                     basis='Published RGB', role='primary')
        errors = []
        check_extended_entry('visual.color_palette', entry, '4111010003: visual.color_palette[0]', errors)
        self.assertTrue(any('RGB' in e or 'rgb' in e for e in errors))

    def test_stale_export_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'ppt-profiles.jsonl'
            path.write_text('stale\n')
            with self.assertRaisesRegex(ValueError, 'Stale PPT export'):
                check_output(path, 'fresh\n')
            self.assertEqual(path.read_text(), 'stale\n')

    def test_official_rgb_selected_with_source(self):
        primary = self.fact(method='official_vi', basis='Published RGB')
        result = colors_for(self.visual(primary))
        self.assertEqual(result['screen_status'], 'official_vi')
        self.assertEqual(result['screen_primary'], primary)

    def test_print_primary_preserves_independent_screen_reference(self):
        primary = self.fact(method='badge_sample', basis='Header sample')
        printing = dict(self.fact(method='official_vi', basis='Published CMYK'),
                        value=None, rgb=None, cmyk=[100, 0, 0, 0], official=True, role='primary')
        result = colors_for(self.visual(primary, [printing]))
        self.assertEqual(result['screen_status'], 'design_reference')
        self.assertEqual(result['screen_primary'], primary)
        self.assertIn('独立来源', result['reason'])
        self.assertEqual(result['primary_fact'], primary)
        self.assertEqual(result['official_print_only'], [printing])
        starter, _, _ = rows_for(self.profile, self.path)
        self.assertEqual(starter['color_primary'], primary['value'])
        self.assertEqual(starter['color_method'], 'badge_sample')
        self.assertEqual(starter['official_print_color_entries'], 1)

    def test_print_primary_without_independent_reference_keeps_empty_screen(self):
        primary = dict(value=None, availability='unresearched')
        printing = dict(self.fact(method='official_vi', basis='Published CMYK'),
                        value=None, rgb=None, cmyk=[100, 0, 0, 0], official=True, role='primary')
        result = colors_for(self.visual(primary, [printing]))
        self.assertEqual(result['screen_status'], 'official_print_only')
        self.assertIsNone(result['screen_primary'])
        self.assertEqual(result['official_print_only'], [printing])
        starter, _, _ = rows_for(self.profile, self.path)
        self.assertIsNone(starter['color_primary'])
        self.assertEqual(starter['color_status'], 'official_print_only')

    def test_partial_print_notation_exports_without_screen_conversion(self):
        self.profile['visual']['color_primary'] = dict(value=None, source=None, availability='unresearched',
            verified='unverified', checked_at=None, search_sources=[])
        self.profile['visual']['color_palette'] = [dict(
            self.fact(method='official_vi', basis='Published partial CMYK'),
            value=None, rgb=None, cmyk=None, cmyk_text='C85 M50', pantone=None,
            label='辅助蓝', official=True, role='primary')]
        record = record_for(self.profile, self.path)
        self.assertEqual(record['colors']['screen_status'], 'official_print_only')
        self.assertIsNone(record['colors']['screen_primary'])
        self.assertEqual(record['colors']['official_print_only'][0]['cmyk_text'], 'C85 M50')
        self.assertEqual(diagnostics(self.export, record, record['school_code']), [])
        for notation in ('C101 M50', 'Cgarbage', ''):
            record['colors']['official_print_only'][0]['cmyk_text'] = notation
            self.assertTrue(diagnostics(self.export, record, record['school_code']))

    def test_conflict_preserves_both_sources(self):
        conflict = dict(self.fact(), value=None, source=None, availability='conflict',
                        candidates=[{'value': '#123456', 'source': 'https://example.edu/one'},
                                    {'value': '#ABCDEF', 'source': 'https://example.edu/two'}])
        result = colors_for(self.visual(conflict))
        self.assertEqual(result['screen_status'], 'conflict')
        self.assertIsNone(result['screen_primary'])
        self.assertEqual(result['conflicts'][0]['fact']['candidates'], conflict['candidates'])

    def test_failed_logo_never_recommended(self):
        asset = {'asset_id': 'a', 'access_status': 'inspection_failed', 'official': True}
        result = logos_for(self.visual(assets=[asset]))
        self.assertEqual(result['status'], 'no_inspected_candidate')
        self.assertIsNone(result['recommended_asset_id'])
        self.assertEqual(result['candidates'][0]['access_status'], 'inspection_failed')

    def test_empty_assets_keep_lookup_state(self):
        result = logos_for(self.visual())
        self.assertEqual(result['status'], 'no_candidate')
        self.assertEqual(result['lookup_status']['vi_url'], self.profile['visual']['vi_url'])

    def test_pdf_mark_preserves_file_and_page_provenance(self):
        path = ROOT / 'universities/河北省/4113013592/profile.yaml'
        profile = load_yaml(path.read_text())
        asset = next(a for a in profile['visual']['logo_assets'] if a.get('download_kind') == 'document_page')
        exported = logos_for(profile['visual'])['candidates'][0]
        for key in ('document_page', 'document_image_sha256', 'document_mark_region', 'sha256', 'format'):
            self.assertEqual(exported[key], asset[key])
        errors = []
        check_extended_entry('visual.logo_assets', asset, 'PDF mark', errors)
        self.assertEqual(errors, [])
        for key, value in [('document_page', 3), ('document_mark_region', [0, 0, 99999, 20]), ('vector', True)]:
            invalid = dict(asset, **{key: value}); errors = []
            check_extended_entry('visual.logo_assets', invalid, 'PDF mark', errors)
            self.assertTrue(errors)

    def test_white_hint_is_not_a_palette(self):
        asset = {'asset_id': 'a', 'access_status': 'content_inspected', 'file_name': 'logo_white.svg'}
        visual = self.visual(assets=[asset])
        result = logos_for(visual)
        self.assertEqual(result['candidates'][0]['preview_background_hint']['value'], 'dark')
        self.assertEqual(visual['color_palette'], [])
        self.assertNotIn('preview_background_hint', visual['logo_assets'][0])

    def test_archive_member_metadata_preserved(self):
        asset = {'asset_id': 'a', 'access_status': 'content_inspected', 'download_kind': 'archive_member',
                 'archive_url': 'https://example.edu/logo.zip', 'url': 'https://example.edu/logo.zip',
                 'archive_member': 'logo/name.png', 'archive_member_display': '标识/name.png', 'archive_sha256': 'a' * 64, 'sha256': 'b' * 64}
        result = logos_for(self.visual(assets=[asset]))
        self.assertEqual(result['candidates'][0]['archive_member'], 'logo/name.png')
        self.assertEqual(result['candidates'][0]['archive_member_display'], '标识/name.png')
        self.assertIn('压缩包入口', result['reason'])
        self.assertEqual(result['candidates'][0]['archive_sha256'], 'a' * 64)

    def test_record_generation_preserves_canonical(self):
        before = copy.deepcopy(self.profile)
        record = record_for(self.profile, self.path)
        self.assertEqual(self.profile, before)
        self.assertEqual(diagnostics(self.export, record, record['school_code']), [])
        for key in ('summary_zh', 'motto', 'founded_year'):
            group = 'overview' if key == 'summary_zh' else 'culture'
            self.assertEqual(record['content'][key], self.profile[group][key])

    def test_export_is_deterministic_and_csv_lossless(self):
        record = record_for(self.profile, self.path)
        self.assertEqual(serialize([record]), serialize([record]))
        row = csv_row(record)
        for key in ('identity', 'logos', 'colors', 'templates', 'content'):
            self.assertEqual(json.loads(row[key + '_json']), record[key])

    def test_all_export_identities_match_scope_and_csv(self):
        with (ROOT / 'data/universities-scope-2026.csv').open(encoding='utf-8-sig', newline='') as handle:
            scope = list(csv.DictReader(handle))
        records = [json.loads(line) for line in (ROOT / 'indexes/ppt-profiles.jsonl').read_text().splitlines()]
        assert_scope(records, scope)
        csv.field_size_limit(32 * 1024 * 1024)
        with (ROOT / 'indexes/ppt-profiles.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r['school_code'] for r in rows], [r['school_code'] for r in records])
        for row, record in zip(rows, records):
            for key in ('identity', 'logos', 'colors', 'templates', 'content'):
                self.assertEqual(json.loads(row[key + '_json']), record[key])

    def test_dynamic_statistics_excluded_from_core_profile(self):
        self.profile['statistics'] = {'student_count': self.fact()}
        self.profile['statistics']['student_count']['value'] = 10
        errors = diagnostics(self.canonical, self.profile, '4111010003')
        self.assertTrue(any('statistics' in e and 'Additional properties' in e for e in errors))

    def test_relabelled_community_color_is_rejected(self):
        self.profile['visual']['color_palette'] = [dict(self.fact(method='community_theme', basis='Community CSS'),
                                                       official=True, role='reference')]
        errors = diagnostics(self.canonical, self.profile, '4111010003')
        self.assertTrue(any('visual.color_palette.0.official' in e for e in errors))

    def test_shared_template_url_keeps_each_source_date(self):
        record = record_for(self.profile, self.path)
        original = {(e['url'], e['source']): e for e in self.profile['visual']['vi_resources']}
        for resource in record['templates']['resources']:
            match = original.get((resource['url'], resource['source']))
            if match:
                self.assertEqual(resource['checked_at'], match['checked_at'])
                self.assertEqual(resource['verified'], match['verified'])

    def test_query_command_returns_exact_identity(self):
        command = [sys.executable, str(ROOT / 'scripts/read_ppt_profile.py'),
                   '--school-code', '4111010003', '--province', '北京市']
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        records = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['school_code'] for r in records], ['4111010003'])

    def test_query_command_unmatched_is_explicit(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/read_ppt_profile.py'),
                                 '--school-code', '0000000000'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('No matching', result.stderr)

    def test_export_schema_rejects_invented_print_screen_value(self):
        record = record_for(self.profile, self.path)
        record['colors']['screen_status'] = 'official_print_only'
        record['colors']['screen_primary'] = self.fact(method='official_vi')
        errors = diagnostics(self.export, record, record['school_code'])
        self.assertTrue(any('colors.screen_primary' in e for e in errors))

    def test_gray_asset_does_not_invent_a_primary(self):
        self.profile['visual']['color_primary'] = dict(value=None, source=None, checked_at=None,
                                                     verified='unverified', availability='unresearched', search_sources=[])
        visual = self.visual(assets=[{'asset_id': 'a', 'access_status': 'content_inspected',
                                     'file_name': 'badge_gray.png'}])
        result = colors_for(visual)
        self.assertIsNone(result['screen_primary'])
        self.assertEqual(result['references'], [])

    def test_loader_rejects_python_object_tags(self):
        with self.assertRaises(Exception):
            load_yaml('!!python/object/apply:os.system ["echo invalid"]')


if __name__ == '__main__':
    unittest.main()
