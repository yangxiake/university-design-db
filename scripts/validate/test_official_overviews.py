import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_official_overviews import extract, date_for, apply_record
from profile_extensions import migrate, empty_fact
from import_additional_public_data import matched_domain_rows
from research_all_schools import same_school


class OverviewExtractionTests(unittest.TestCase):
    def extract(self, lines):
        return extract('测试大学','测试大学-学校简介', ['测试大学是一所位于某省的本科高校，学校面向社会开展教育教学和科学研究，已有多个校区与专业设置。'*3]+lines,'https://example.edu.cn/about')

    def test_unit_and_approximate_basis(self):
        claims,_=self.extract(['学校全日制在校生约2.5万人，现有教职工1800余人，学校占地面积1500亩。截至2025年9月，学校持续开展教学。'])
        facts={c['field']:c for c in claims}
        self.assertEqual(facts['statistics.student_count']['value'],25000)
        self.assertTrue(facts['statistics.student_count']['approximate'])
        self.assertEqual(facts['statistics.campus_area_hectares']['value'],100)
        self.assertEqual(facts['statistics.faculty_count']['source_as_of'],'2025-09')

    def test_no_date_is_not_fetch_date(self):
        claims,_=self.extract(['学校全日制在校生25000人，拥有教职工1800人，本科专业设置覆盖多个学科领域。'])
        self.assertEqual(claims[0]['source_as_of'],'undated')
        self.assertEqual(date_for('学校始建于1950年，2026年发布学校简介。','')[0],'undated')

    def test_historical_planned_and_ambiguous_counts(self):
        claims,_=self.extract(['建校初在校生1000人，学校计划在校生30000人，正在规划新校区。'])
        self.assertFalse(claims)
        claims,_=self.extract(['学校在校生22000人，其中另一统计表列在校生25000人，教学科研稳定开展。'])
        self.assertFalse(any(c['field']=='statistics.student_count' for c in claims))

    def test_campus_list_does_not_capture_management_history(self):
        _,campuses=self.extract(['学校先后隶属原中国有色金属工业总公司管理，现已建成呈贡、莲华、新迎三个校区，正在全力推进新校区建设。'])
        # Planned campuses are excluded; reject the paragraph rather than invent
        # a campus called色金属工业总公司管理.
        self.assertFalse(any('管理' in c['name'] or '建成' in c['name'] for c in campuses))
        _,campuses=self.extract(['学校现拥有新城、金川、康巴什三个校区，办学条件日益完善，形成综合办学体系。'])
        self.assertEqual([c['name'] for c in campuses],['新城校区','金川校区','康巴什校区'])

    def test_professional_degree_basis_is_preserved(self):
        claims,_=self.extract(['学校现有专业硕士学位授权点30个，硕士学位一级学科授权点49个，形成多学科的教学与人才培养体系。'])
        values=next(c['value'] for c in claims if c['field']=='academics.degree_authorizations')
        self.assertIn('专业硕士学位授权点',values[0])
        self.assertIn('一级学科',values[1])

    def test_wrong_school_and_department_are_excluded(self):
        lines=['测试大学是一所本科高校。'*20,'学校在校生30000人，教职工2000人，办学条件完善。']
        self.assertFalse(extract('测试大学','测试大学机械学院简介',lines,'https://example.edu.cn/about')[0])

    def test_domain_matching_does_not_use_parent_domain(self):
        def profile(home, english):
            return {'identity':{'official_website':{'value':home},'name_en':{'value':english}}}
        profiles={'mother':profile('https://www.school.edu.cn','Main University'),
                  'independent':profile('https://college.school.edu.cn','Independent College')}
        rows=[dict(country='China',name='Unknown College',domains=['new.school.edu.cn']),
              dict(country='China',name='Main University',domains=['school.edu.cn'])]
        matches,gaps=matched_domain_rows(rows,profiles)
        self.assertEqual([r['school_code'] for r in matches],['mother'])
        self.assertEqual(len(gaps),1)

    def test_international_subgroup_and_new_campus_are_not_totals(self):
        claims,_=self.extract(['学校有留学生495人（其中：本科生311人、硕士生100人），正在建设新校区，新校区位于城区东南，占地面积1120亩。'])
        self.assertFalse(any(c['field'] in {'statistics.student_count','statistics.campus_area_hectares'} for c in claims))

    def test_cn_registration_suffix_is_not_an_institution(self):
        self.assertFalse(same_school('https://other.com.cn/page','https://school.com.cn'))
        self.assertTrue(same_school('https://info.school.com.cn/page','https://school.com.cn'))

    def test_reparse_retracts_only_owned_automatic_claims(self):
        profile=migrate({'identity':{}})
        source='https://example.edu.cn/about'
        profile['statistics']['student_count']=dict(empty_fact(),value=30000,source=source,verified='human',availability='found')
        profile['statistics']['faculty_count']=dict(empty_fact(),value=2000,source=source,verified='auto',availability='found',collector='official_overview')
        apply_record(profile,dict(checked_at='2026-10-01',pages=[{'source_url':source}],claims=[],campuses=[]))
        self.assertEqual(profile['statistics']['student_count']['value'],30000)
        self.assertIsNone(profile['statistics']['faculty_count']['value'])


if __name__=='__main__':unittest.main()
