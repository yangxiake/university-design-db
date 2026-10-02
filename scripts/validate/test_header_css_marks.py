import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_header_css_marks import HeaderPage,css_candidates,is_header_reference


class HeaderCssTests(unittest.TestCase):
    def test_relative_logo_background_is_resolved_against_stylesheet(self):
        result=css_candidates('.header .logo{background:url(../img/abc.png)}','https://u.edu.cn/css/a.css')
        self.assertEqual(result[0]['src'],'https://u.edu.cn/img/abc.png')

    def test_footer_qrcode_and_banner_are_not_logo_candidates(self):
        text='.footer .logo{background:url(logo.png)} .qrcode .logo{background:url(logo.png)} .header{background:url(hero.jpg)}'
        self.assertEqual(css_candidates(text,'https://u.edu.cn/a.css'),[])

    def test_lazy_header_image_is_found_but_footer_is_not(self):
        page=HeaderPage();page.feed('<div class="logo"><img data-original="/mark.png"></div><footer class="logo"><img src="/footer.png"></footer>');page.finish()
        self.assertEqual([a['src'] for a in page.extra_images],['/mark.png'])

    def test_late_news_party_and_browser_icons_are_not_header_marks(self):
        for image in [dict(src='/logo.png',context='news',position=30),dict(src='/djlogo.png',context='logo',position=1),dict(src='/logo.png',context='#browser-modal .logo',css_url='https://u.edu.cn/a.css')]:
            self.assertFalse(is_header_reference(image))
        self.assertTrue(is_header_reference(dict(src='/encoded.png',context='header logo',position=27)))


if __name__=='__main__':unittest.main()
