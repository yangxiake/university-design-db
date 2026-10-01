import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_ppt_resources import VisualPage,TemplateBlocks,entries
from build_ppt_indexes import logo_score,community_category


class PptResourceTests(unittest.TestCase):
    def test_generic_download_is_bound_to_template_card(self):
        html='<title>PPT模版-测试大学</title><div><a href="/a.pptx">下载</a><p>2026年PPT模版9</p></div>'
        page=VisualPage();page.feed(html);page.finish();blocks=TemplateBlocks();blocks.feed(html);page.template_links=blocks.links
        result=entries(page,'https://example.edu.cn/templates','a'*64,dict(publisher='测试大学',use_scope='school'))
        file=next(e for e in result if e['url'].endswith('.pptx'))
        self.assertEqual(file['edition_year'],2026)
        self.assertEqual(file['formats'],['PPTX'])

    def test_self_navigation_does_not_overwrite_read_page(self):
        page=VisualPage();page.feed('<title>PPT模板-测试大学</title><a href="/templates">PPT模板</a>');page.finish()
        result=entries(page,'https://example.edu.cn/templates','a'*64,dict(publisher='测试大学',use_scope='school'))
        self.assertEqual(len(result),1)
        self.assertTrue(result[0]['content_read'])

    def test_department_scope_and_date_are_not_relabelled(self):
        page=VisualPage();page.feed('<a href="/a.pptx">2025-12-03学院PPT模板.pptx</a>');page.finish()
        result=entries(page,'https://example.edu.cn/templates','a'*64,dict(publisher='测试大学法学院',use_scope='department'))
        file=next(e for e in result if e['url'].endswith('.pptx'))
        self.assertNotIn('edition_year',file)
        self.assertEqual(file['use_scope'],'department')

    def test_logo_order_preserves_access_and_official_status(self):
        official=dict(access_status='content_inspected',official=True,kind='site_identity',vector=False)
        community=dict(access_status='content_inspected',official=False,kind='badge',vector=True)
        uninspected=dict(access_status='indexed_not_fetched',official=True,kind='badge',vector=True)
        self.assertGreater(logo_score(official),logo_score(community))
        self.assertGreater(logo_score(community),logo_score(uninspected))

    def test_logo_and_history_references_are_not_presentation_templates(self):
        self.assertEqual(community_category('logo_reference'),'community_logo_reference')
        self.assertEqual(community_category('history_reference'),'community_history_reference')
        self.assertEqual(community_category('beamer_theme'),'community_template')


if __name__=='__main__':unittest.main()
