"""Regression checks for institution subjects and bounded official research."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ingest"))
from research_all_schools import extract_claims, same_school
from import_research_claims import choose_claims
from merge_research_passes import merge


class ResearchExtractionTest(unittest.TestCase):
    def extract(self, text, title="学校简介-示例大学", kind="overview"):
        return extract_claims("示例大学", kind, title, text, "https://www.example.edu.cn/about.htm")

    def test_department_year_is_not_school_founding(self):
        self.assertEqual(self.extract("示例大学经济学院创建于2001年。学校创建于1950年。")[0]["value"], 1950)
        self.assertEqual(self.extract("学校的附属小学创建于2001年。"), [])
        self.assertEqual(self.extract("示例大学坐落于示例市，是一所综合性大学，始建于1950年。")[0]["value"], 1950)
        self.assertEqual(self.extract("学校的经济学院始建于2001年。"), [])
        self.assertEqual(self.extract("学校是由1950年成立的学校合并组成。"), [])
        self.assertEqual(self.extract("学校创建于1898年。", title="北京大学章程-示例大学", kind="charter"), [])
        self.assertEqual(self.extract("学校位于示例市，创建于2999年。"), [])
        self.assertEqual(extract_claims("中国矿业大学", "charter", "中国矿业大学（北京）章程",
                         "学校创建于1978年。", "https://www.moe.gov.cn/example.html"), [])

    def test_only_explicit_motto_not_generic_quoted_slogan(self):
        self.assertEqual(self.extract("学校秉承“厚德博学”的校训。")[0]["value"], "厚德博学")
        self.assertEqual(self.extract("学校坚持“为党育人”的办学方向。"), [])
        self.assertEqual(self.extract("示例大学校训：崇德尚文：提高道德素养；兼收并蓄：促进交流。"), [])

    def test_navigation_before_first_sentence_does_not_hide_year(self):
        values = self.extract("学校简介\n信息公开\n学校创建于1950年。")
        self.assertEqual(values[0]["value"], 1950)
        origin = self.extract("序言\n学校前身是1950年创办的示例师范学校。")
        self.assertEqual(origin[0]["value"], 1950)
        self.assertIn("前身起源", origin[0]["basis"])
        self.assertEqual(self.extract("示例大学附属学校创建于2001年。"), [])
        self.assertEqual(self.extract("学院英文名称为Example College。", title="经济学院-示例大学"), [])

    def test_english_is_not_translated_or_department_title(self):
        self.assertEqual(self.extract("示例大学英文名称为Example University。")[0]["value"], "Example University")
        self.assertEqual(self.extract("", title="示例大学-Example University")[0]["value"], "Example University")
        self.assertEqual(self.extract("", title="经济学院-Example University"), [])

    def test_alternate_visual_links_are_not_color_conflict(self):
        choices = [dict(value="https://vi.example.edu.cn/logo.htm", source="https://vi.example.edu.cn/logo.htm"),
                   dict(value="https://vi.example.edu.cn/", source="https://vi.example.edu.cn/")]
        self.assertEqual(len(choose_claims("visual.vi_url", choices)), 1)
        self.assertEqual(len(choose_claims("culture.founded_year", [dict(value=1950), dict(value=2001)])), 2)

    def test_external_redirect_cannot_be_school_evidence(self):
        self.assertTrue(same_school("https://vi.example.edu.cn/", "https://www.example.edu.cn/"))
        self.assertFalse(same_school("https://example.edu.cn.evil.com/", "https://www.example.edu.cn/"))

    def test_reread_replaces_partial_claim_but_preserves_other_sources(self):
        a, b = "https://www.example.edu.cn/motto.htm", "https://www.example.edu.cn/about.htm"
        base = dict(checked_at="2026-10-01", home=b, pages=[],
                    claims=[dict(field="culture.motto", value="崇德尚文", source=a),
                            dict(field="culture.motto", value="崇德尚文兼收并蓄", source=b)])
        update = dict(checked_at="2026-10-01", pages=[dict(requested_url=a, source_url=a, status="read")], claims=[])
        result = merge(base, update, {})
        self.assertEqual([c["source"] for c in result["claims"]], [b])
        self.assertEqual(result["status"], "researched_partial")


if __name__ == "__main__":
    unittest.main()
