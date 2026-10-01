"""Guard source identity and parsing boundaries introduced by the scope expansion."""
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from import_public_repositories import read_objects, directory_candidates, normalize
from discover_official_pages import matches_school_title, read_bounded
from render_community import render

class SourceBoundaryTests(unittest.TestCase):
    def test_concatenated_json_is_data_not_executable(self):
        self.assertEqual(read_objects('{"name":"甲"}\n{"name":"乙"}'),[{'name':'甲'},{'name':'乙'}])
        with self.assertRaises(ValueError):read_objects("__import__('os').system('true')")

    def test_parent_and_independent_college_titles_are_distinct(self):
        names=['辽宁中医药大学','辽宁中医药大学杏林学院','湖南大学','网络空间安全学院']
        self.assertFalse(matches_school_title(names[0],names[1],names))
        self.assertTrue(matches_school_title(names[1],names[1],names))
        self.assertFalse(matches_school_title(names[3],'湖南大学网络空间安全学院',names))

    def test_renamed_school_can_show_its_former_parent(self):
        self.assertTrue(matches_school_title('广州新华学院','广州新华学院-(原)中山大学新华学院',['广州新华学院','中山大学']))

    def test_split_anchor_names_do_not_attach_to_parent(self):
        schools={normalize('湖北大学'):{'school_code':'parent'},normalize('湖北大学知行学院'):{'school_code':'independent'}}
        links=directory_candidates('¥ 湖北大学<a href="https://college.example/">知行学院</a>',schools)
        self.assertEqual(links[0][0]['school_code'],'independent')

    def test_directory_without_http_href_keeps_explicit_domain_candidate(self):
        schools={'网络空间安全学院':{'school_code':'new'}}
        links=directory_candidates('<a href="中国网谷" title="www.csuc.edu.cn">网络空间安全学院</a>',schools)
        self.assertEqual(links[0][1],'https://www.csuc.edu.cn')

    def test_response_size_limit_rejects_truncated_evidence(self):
        import io
        with self.assertRaises(ValueError):read_bounded(io.BytesIO(b'abcdef'),3)
        self.assertEqual(read_bounded(io.BytesIO(b'abc'),3),b'abc')

    def test_historical_institution_motto_is_not_current_motto(self):
        from research_all_schools import extract_claims
        old=extract_claims('中国人民大学','history','中国人民大学校史',
                           '华北联合大学的教育方针是培养革命干部，校训是“团结、前进、刻苦、坚定”。',
                           'https://www.ruc.edu.cn/lishiyange.html')
        self.assertFalse(any(c['field']=='culture.motto' for c in old))
        current=extract_claims('中国人民大学','charter','中国人民大学章程',
                               '中国人民大学以“实事求是”为校训。','https://xxgk.ruc.edu.cn/charter.htm')
        self.assertTrue(any(c['field']=='culture.motto' and c['value']=='实事求是' for c in current))

    def test_retracted_sources_are_not_reintroduced(self):
        import csv, json, yaml
        root=pathlib.Path(__file__).resolve().parents[2]
        with (root/'data/universities-scope-2026.csv').open(encoding='utf-8-sig') as handle:
            scope={r['school_code']:r for r in csv.DictReader(handle)}
        for line in (root/'data/review/identity-corrections-2026.jsonl').read_text().splitlines():
            correction=json.loads(line);row=scope[correction['school_code']]
            profile=yaml.safe_load((root/'universities'/row['province']/row['school_code']/'profile.yaml').read_text())
            group,key=correction['field'].split('.')
            self.assertNotEqual(profile[group][key].get('source'),correction['old_fact']['source'])

    def test_no_empty_community_view(self):
        self.assertIsNone(render({'identity':{'name_zh':'甲校'},'resources':{}}))

if __name__=='__main__':unittest.main()
