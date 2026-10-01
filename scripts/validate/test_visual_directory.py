import pathlib
import sys
import unittest
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_visual_directory import VisualPage, visual_heading, page_identity, directory_leads, resource_entry, recover_cached_pages


class VisualDirectoryTests(unittest.TestCase):
    def page(self,text):
        page=VisualPage();page.feed(text);return page.finish()

    def test_standard_export_news_is_not_school_emblem(self):
        page=self.page('<title>我校标准出海项目-柳州职业技术大学</title><h1>我校标准出海项目</h1>')
        self.assertFalse(visual_heading(page))

    def test_navigation_heading_is_not_page_subject(self):
        page=self.page('<title>教学通知-测试大学</title><nav><h3>校徽</h3></nav><h1>教学通知</h1>')
        self.assertFalse(visual_heading(page))

    def test_foreign_school_and_news_mention_are_not_identity(self):
        page=self.page('<title>清华大学校徽-北京大学</title><p>北京大学版权所有</p>')
        self.assertFalse(page_identity('北京大学',page))
        page=self.page('<title>校徽发布</title><p>受邀到北京大学开展活动</p>')
        self.assertFalse(page_identity('北京大学',page))

    def test_introduction_and_anniversary_categories(self):
        entry=resource_entry('校徽校训','https://example.edu.cn/badge','https://example.edu.cn/badge','a'*64)
        self.assertEqual(entry['kinds'],['校徽/校名介绍及资源'])
        special=resource_entry('120周年视觉识别手册','https://example.edu.cn/a.pdf','https://example.edu.cn/badge','a'*64,True,'PDF')
        self.assertIn('校庆专用',special['kinds'])

    def test_directory_matches_full_current_school_name(self):
        cells=['1','北京大学','北京','<a href="https://www.pku.edu.cn">官网</a>','<a href="https://vim.pku.edu.cn">查看</a>','暂无','标识']
        body=('<table><tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr></table>').encode()
        rows=directory_leads(body,'utf-8',{'北京大学':'4111010001'})
        self.assertEqual(rows[0]['visual_leads'],['https://vim.pku.edu.cn'])
        self.assertFalse(directory_leads(body,'utf-8',{'北京大学医学部':'other'}))

    def test_generic_title_recovery_requires_exact_confirmed_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);cache=root/'tmp/visual-directory';cache.mkdir(parents=True)
            sha='a'*64;(cache/('code-'+sha[:16]+'.html')).write_text('<title>学校标识</title><p>北京大学是一所高校。</p>')
            def record(host):
                return {'code':dict(name_zh='北京大学',pages=[dict(detail='school_identity_gap',source_url='https://'+host+'/logo',source_sha256=sha)],resources=[])}
            profiles={'code':{'identity':{'official_website':{'value':'https://www.pku.edu.cn'}}}}
            with patch('collect_visual_directory.ROOT',root):
                wrong=record('department.pku.edu.cn');recover_cached_pages(wrong,profiles)
                self.assertFalse(wrong['code']['resources'])
                own=record('www.pku.edu.cn');recover_cached_pages(own,profiles)
                self.assertEqual(len(own['code']['resources']),1)


if __name__=='__main__':unittest.main()
