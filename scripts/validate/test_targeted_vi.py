"""Guard source receipts against login pages and false attachment read claims."""
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'ingest'))
import collect_targeted_vi as collector
from collect_header_css_marks import HeaderPage, is_header_reference
from import_targeted_resources import resource_from_receipt


class TargetedVITests(unittest.TestCase):
    def target(self):
        return dict(school_code='4150010635', name_zh='西南大学', home='https://www.swu.edu.cn/',
                    url='https://www.swu.edu.cn/vi', purpose='官方VI')

    def test_school_login_page_is_not_read_vi_content(self):
        body='<title>西南大学统一登录</title><input type = "password">'.encode()
        with patch.object(collector, 'fetch', return_value=('https://www.swu.edu.cn/vi', body, 'utf-8', 'text/html')):
            result=collector.collect(self.target())
        self.assertEqual(result['status'], 'access_gap')
        self.assertEqual(result['attempts'][0]['detail'], 'authentication_required')
        self.assertNotIn('images', result)

    def test_pdf_compatibility_glyphs_match_but_scanned_identity_needs_review(self):
        with tempfile.TemporaryDirectory() as directory:
            reader=types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=lambda: '西南⼤学')])
            with patch.object(collector, 'ROOT', pathlib.Path(directory)), patch.object(collector, 'PdfReader', return_value=reader), patch.object(collector, 'fetch', return_value=('https://www.swu.edu.cn/vi.pdf', b'%PDF-test', None, 'application/pdf')):
                matched=collector.collect(self.target())
                reader.pages[0].extract_text=lambda: ''
                scanned=collector.collect(self.target())
        self.assertTrue(matched['identity_match'])
        self.assertFalse(scanned['identity_match'])
        self.assertEqual(scanned['identity_review'], 'requires_visual_review')

    def test_menu_layout_keeps_header_logo_and_rejects_navigation_buttons(self):
        page=HeaderPage()
        page.feed('<header><div class="menu-mod header_logo"><div class="logo"><img src="/school.png"><img src="/menu.png"><img src="/search_icon.png"></div></div></header>')
        refs=[i for i in page.extra_images if is_header_reference(i)]
        self.assertEqual([i['src'] for i in refs], ['/school.png'])
        self.assertFalse(is_header_reference(dict(src='/logo_jw.png', context='logo', position=1)))

    def test_read_publication_page_does_not_mark_linked_zip_as_read(self):
        source=dict(url='https://www.swu.edu.cn/vi', resolved_url='https://www.swu.edu.cn/vi',
                    checked_at='2026-10-02', status='source_read', format='HTML',
                    links=[dict(url='https://www.swu.edu.cn/logo.zip')], source_sha256='a'*64)
        spec=dict(receipt_url=source['url'], url='https://www.swu.edu.cn/logo.zip')
        result=resource_from_receipt(spec,source)
        self.assertFalse(result['content_read'])
        self.assertEqual(result['download_status'],'indexed_not_fetched')
        self.assertIn('receipt_url',spec)
        with self.assertRaisesRegex(ValueError,'not present'):
            resource_from_receipt(dict(spec,url='https://www.swu.edu.cn/not-linked.zip'),source)


if __name__=='__main__':
    unittest.main()
