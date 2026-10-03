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
from import_targeted_resources import resource_from_receipt, reviewed_asset
from import_visual_refresh import enrich_screen_metadata, merge_official_color
from validate_profiles import check_template_file


class TargetedVITests(unittest.TestCase):
    def test_document_metadata_requires_actual_pdf_read_and_positive_pages(self):
        entry=dict(content_read=True,download_status='pdf_read',document_metadata=dict(format='PDF',page_count=2,sha256='a'*64,byte_size=100))
        errors=[];check_template_file(entry,'PDF',errors);self.assertFalse(errors)
        for invalid in [dict(entry,content_read=False),dict(entry,download_status='indexed_not_fetched'),dict(entry,document_metadata=dict(entry['document_metadata'],page_count=0))]:
            errors=[];check_template_file(invalid,'PDF',errors);self.assertTrue(errors)

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

    def test_svg_read_requires_visual_identity_and_rejects_active_content(self):
        target=self.target()
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, 'ROOT', pathlib.Path(directory)):
            for body, expected in [(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20"><path d="M0 0L40 20"/></svg>', 'source_read'),
                                   (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', 'access_gap')]:
                with patch.object(collector, 'fetch', return_value=(target['url'], body, None, 'image/svg+xml')):
                    result=collector.collect(target)
                self.assertEqual(result['status'], expected)
                if expected == 'source_read':
                    self.assertTrue(result['vector'])
                    self.assertFalse(result['identity_match'])
                    self.assertEqual(result['identity_review'], 'requires_visual_review')

    def test_reviewed_graphic_rejects_old_name_and_foreign_publication(self):
        identity=dict(school_code='4150010635',name_zh='西南大学',official_website=dict(value='https://www.swu.edu.cn/'))
        spec=dict(identity_text='旧校名',source='https://www.swu.edu.cn/')
        with self.assertRaisesRegex(ValueError,'different school name'):
            reviewed_asset(spec, {}, identity)
        spec.update(identity_text=identity['name_zh'],source='https://other.edu.cn/')
        with self.assertRaisesRegex(ValueError,'outside the confirmed'):
            reviewed_asset(spec, {}, identity)

    def test_pdf_receipt_does_not_pretend_to_be_presentation_structure(self):
        source=dict(url='https://www.swu.edu.cn/vi.pdf',resolved_url='https://www.swu.edu.cn/vi.pdf',status='source_read',format='PDF',
            checked_at='2026-10-02',source_sha256='a'*64,byte_size=1000,page_count=4,identity_match=False)
        spec=dict(receipt_url=source['url'],url=source['url'])
        with self.assertRaisesRegex(ValueError,'visual review'):resource_from_receipt(spec,source)
        result=resource_from_receipt(dict(spec,document_identity_reviewed=True),source)
        self.assertTrue(result['content_read'])
        self.assertEqual(result['document_metadata']['page_count'],4)
        self.assertNotIn('file_metadata',result)

    def test_official_metadata_enrichment_preserves_human_or_conflicting_values(self):
        spec=dict(value='#003F88',cmyk=[100,70,0,25],pantone=None,label='标准蓝')
        current=dict(value='#003F88',method='official_vi',verified='auto',cmyk=None,pantone=None)
        enrich_screen_metadata(current,spec)
        self.assertEqual(current['cmyk'],spec['cmyk'])
        for protected in [dict(current,verified='human',cmyk=None),dict(current,value='#123456',cmyk=None),dict(current,method='manual_derived',cmyk=None),dict(current,cmyk=[0,0,0,0])]:
            before=dict(protected);enrich_screen_metadata(protected,spec)
            self.assertEqual(protected,before)
        entry=dict(value='#003F88',source='https://www.school.edu.cn/vi',method='official_vi',label=None,verified='auto',cmyk=None)
        palette=[entry];new=dict(entry,**spec)
        merge_official_color(palette,new)
        merge_official_color(palette,new)
        self.assertEqual(len(palette),1)
        self.assertEqual(palette[0]['cmyk'],spec['cmyk'])


if __name__=='__main__':
    unittest.main()
