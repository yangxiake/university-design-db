"""Keep the narrowed scope and source identity intact across collection paths."""
import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from ppt_scope import core_profile, SCOPE
from profile_extensions import migrate, put_fact
from collect_english_names import title_name, field_name
from collect_wikidata_core import claims_for
from ppt_core_extraction import additional_claims
from collect_ppt_site_colors import candidates, school_stylesheets
from collect_wikipedia_core import core_claims, fields
from fill_monochrome_primary import archive_name
from collect_chinaschool_core import info_claims
from yaml_io import load_yaml
from validate_schemas import schema_validator, diagnostics
from report_ppt_core import required_gaps


class PPTCoreTests(unittest.TestCase):
    def test_print_only_primary_is_a_screen_gap_despite_recorded_sample(self):
        p = load_yaml((ROOT / 'universities/北京市/4111010003/profile.yaml').read_text(encoding='utf-8'))
        p['visual']['color_primary'] = dict(value='#123456', availability='found', method='badge_sample')
        p['visual']['color_palette'] = [dict(value=None, rgb=None, cmyk=[100, 0, 0, 0],
                                           method='official_vi', official=True, role='primary')]
        gaps, recorded_gaps, status = required_gaps(p)
        self.assertEqual(status, 'official_print_only')
        self.assertIn('visual.color_primary', gaps)
        self.assertNotIn('visual.color_primary', recorded_gaps)
        p['visual']['color_primary']['method'] = 'official_vi'
        self.assertNotIn('visual.color_primary', required_gaps(p)[0])

    def test_current_projection_validates_registry_note_and_optional_culture_lists(self):
        p = load_yaml((ROOT / 'universities/北京市/4111010003/profile.yaml').read_text(encoding='utf-8'))
        p = core_profile(p)
        p['visual']['landmarks'] = [dict(name='示例地标', source='https://www.tsinghua.edu.cn/',
                                       checked_at='2026-10-03', verified='auto')]
        validator = schema_validator('profile-schema-v4.json')
        self.assertEqual(diagnostics(validator, p, p['identity']['school_code']), [])
        p['statistics'] = {'student_count': {}}
        self.assertTrue(diagnostics(validator, p, p['identity']['school_code']))

    def test_projection_removes_data_and_copied_summary_but_preserves_visual_proof(self):
        profile = load_yaml((ROOT / 'universities/北京市/4111010003/profile.yaml').read_text(encoding='utf-8'))
        profile['statistics'] = {'student_count': {'value': 999999}}
        profile['admissions'] = {'cutoffs': [{'minimum_score': 700}]}
        profile['overview']['summary_zh']['value'] = '就业率99%，排名第一'
        proof = copy.deepcopy(profile['visual'])
        result = core_profile(profile)
        self.assertNotIn('statistics', result); self.assertNotIn('admissions', result)
        self.assertNotIn('就业', result['overview']['summary_zh']['value'])
        self.assertEqual(result['visual'], proof)
        self.assertEqual(core_profile(result), result)
        self.assertEqual(migrate(result), result)
        with self.assertRaisesRegex(ValueError, 'excluded'):
            put_fact(result, 'employment.summary', 'new report', {})
        self.assertNotIn('culture.motto', SCOPE['required_facts'])

    def test_english_main_title_excludes_department_and_navigation_text(self):
        self.assertEqual(title_name('Welcome to Example University - English'), 'Example University')
        self.assertEqual(title_name('Wuhan Conservatory of Music'), 'Wuhan Conservatory of Music')
        self.assertEqual(field_name('Medicine & Technology School Of Zunyi Medical University'), 'Medicine & Technology School Of Zunyi Medical University')
        self.assertEqual(field_name('Example College，Example University'), 'Example College,Example University')
        for title in ('Department of Physics - Example University', 'School of Law, Example University',
                      'Admissions Office of Example College', '首页', 'Example University 2026 News'):
            self.assertIsNone(title_name(title))

    def test_wikidata_identity_period_and_ambiguous_years(self):
        def statement(year):
            return dict(rank='normal', id='Q1$statement', mainsnak=dict(snaktype='value', datavalue=dict(value=dict(
                time='+%s-01-01T00:00:00Z' % year, precision=9, before=0, after=0))))
        entity = dict(labels={'zh': {'value': '示例大学'}}, descriptions={'zh': {'value': '中国的一所大学'}},
                      claims={'P571': [statement(1950)]})
        claims, status = claims_for(entity, '示例大学', True)
        self.assertEqual(status, 'exact_school_matched'); self.assertEqual(claims[0]['value'], 1950)
        self.assertEqual(claims_for(entity, '另一大学')[1], 'exact_chinese_name_gap')
        entity['claims']['P571'].append(statement(2001))
        self.assertFalse(claims_for(entity, '示例大学')[0])
        entity['claims']['P571'] = [dict(statement(1950), qualifiers={'P582': []})]
        self.assertFalse(claims_for(entity, '示例大学')[0])
        entity['descriptions']['zh']['value'] = '一支大学足球队'
        self.assertEqual(claims_for(entity, '示例大学', True)[1], 'education_entity_identity_gap')

    def test_founding_origin_and_current_year_stay_distinct(self):
        claims = additional_claims('示例大学', 'overview', '示例大学简介', '示例大学前身是1954年成立的师范学校。', 'https://example.edu.cn/about')
        self.assertEqual(claims[0]['value'], 1954); self.assertIn('前身', claims[0]['basis'])
        self.assertEqual(additional_claims('示例大学', 'overview', '示例大学简介', '学校新校区于2021年成立。', 'https://example.edu.cn/about'), [])
        self.assertEqual(additional_claims('示例大学', 'overview', '新闻', '示例大学成立于1950年。', 'https://example.edu.cn/news'), [])
        claims = additional_claims('示例大学', 'overview', '示例大学简介', '示例大学1997年由示例投资集团出资创办。', 'https://example.edu.cn/about')
        self.assertEqual(claims[0]['value'], 1997)
        self.assertFalse(additional_claims('示例大学', 'overview', '示例大学简介', '示例大学产业学院1997年由集团出资创办。', 'https://example.edu.cn/about'))

    def test_css_reference_requires_existing_whole_header_region(self):
        css = '.header {background:#123456}.news{background:#900}.nav li{background:#321}.nav:hover{background:#777}.absent-nav{background:#000}'
        found = candidates(css, {'header', 'nav'}, set())
        self.assertEqual([c['value'] for c in found], ['#123456'])
        self.assertEqual(candidates('.header{background:linear-gradient(#123,#456)}', {'header'}, set()), [])
        self.assertEqual(candidates('.header2 .item{background:#333}', {'header2', 'item'}, set()), [])
        self.assertEqual(candidates('.head2{background:#ED5713}', {'head2'}, set())[0]['value'], '#ED5713')

    def test_site_styles_come_before_framework_and_existing_head_variants_are_read(self):
        styles = ['/_css/_system/system.css', '/_js/plugin/calendar.css', '/css/swiper.min.css',
                  '/css/slick.css', '/css/reset.css', '/css/newindex.css', '/css/site.css']
        self.assertEqual(school_stylesheets(styles)[:2], ['/css/newindex.css', '/css/site.css'])
        css = '.g-head{background:#1046a6}.top_info_bg{background:#3D3BB8}.head_bg.on{background:#123456}'
        self.assertEqual([c['value'] for c in candidates(css, {'g-head', 'top_info_bg', 'head_bg'}, set())],
                         ['#1046A6', '#3D3BB8'])

    def test_wikipedia_multiple_years_and_article_prose_do_not_become_infobox_facts(self):
        text = '{{高校\n| name=示例大学\n| EnglishName=Example University\n| established=1950年（2001年更名）\n}}\n1950年分校成立'
        claims, _ = core_claims(text)
        self.assertEqual([c['field'] for c in claims], ['identity.name_en'])
        self.assertEqual(core_claims('示例大学1950年成立')[0], [])
        self.assertEqual(fields('{{高校\n|image=\n|EnglishName=Example University\n}}')['image'], '')

    def test_chinese_zip_display_name_matches_without_changing_container(self):
        class Member:
            flag_bits = 0
            filename = 'img2/北京建筑大学.png'.encode('gb18030').decode('cp437')
        self.assertEqual(archive_name(Member()), 'img2/北京建筑大学.png')

    def test_secondary_info_block_requires_exact_current_school_name(self):
        lines = [(False,t) for t in ['中文名','示例大学独立学院','外文名','Example College','创办时间','2004年']]
        self.assertEqual(info_claims('示例大学',lines),[])
        self.assertEqual(len(info_claims('示例大学独立学院',lines)),2)


if __name__ == '__main__':
    unittest.main()
