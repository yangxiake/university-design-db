"""School ownership must not be inferred from a news mention or parent name."""
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_homepage_identity import ownership_evidence,is_school_homepage


class HomepageIdentityTests(unittest.TestCase):
    def test_complete_copyright_owner_accepts_generic_title(self):
        names=['测试大学','测试大学独立学院']
        self.assertTrue(ownership_evidence('测试大学',['Copyright © 测试大学 All Rights Reserved.'],names))
        self.assertTrue(ownership_evidence('测试大学',['测试大学 版权所有'],names))
        self.assertTrue(ownership_evidence('测试大学独立学院',['版权所有：测试大学独立学院 2026'],names))

    def test_news_mention_and_parent_owner_are_insufficient(self):
        names=['测试大学','测试大学独立学院']
        self.assertIsNone(ownership_evidence('测试大学',['测试大学来访交流'],names))
        self.assertIsNone(ownership_evidence('测试大学独立学院',['版权所有：测试大学'],names))
        self.assertIsNone(ownership_evidence('测试大学',['Copyright © 测试大学独立学院'],names))

    def test_former_owner_and_recycled_site_are_not_current_proof(self):
        self.assertIsNone(ownership_evidence('新的职业大学',['版权所有：旧名职业学院'],['新的职业大学']))
        self.assertIsNone(ownership_evidence('海都学院',['Copyright © 好读小说网'],['海都学院']))

    def test_owned_admissions_portal_is_not_school_homepage(self):
        self.assertFalse(is_school_homepage('https://zsxx.hrbu.edu.cn/'))
        self.assertFalse(is_school_homepage('https://english.example.edu.cn/'))
        self.assertTrue(is_school_homepage('https://klc.qhu.edu.cn/'))
        self.assertTrue(is_school_homepage('https://www.hrbu.edu.cn/'))


if __name__=='__main__':unittest.main()
