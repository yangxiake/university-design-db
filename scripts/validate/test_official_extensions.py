"""Guard against mixing news, footer compliance marks and school contacts."""
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_official_extensions import Page,contact_claims,portal_claims,apply_record,sanitize_record
from profile_extensions import migrate
from render_enriched import render_visual


def page(html):
    p=Page();p.feed(html);return p.finish()


class OfficialExtensionTests(unittest.TestCase):
    def test_inline_contact_labels_survive_and_news_contacts_are_excluded(self):
        p=page('<title>测试大学</title><article>地址：别处路1号 电话：010-12345678</article>'
               '<footer><p><span>地址：</span><b>测试市大学路2号</b> | 邮编：100084</p>'
               '<p>招生咨询电话：010-87654321</p><p>传真：010-33333333</p>'
               '<p>技术支持电话：010-44444444</p></footer>')
        claims={c['field']:c['value'] for c in contact_claims(p,'homepage')}
        self.assertEqual(claims['location.address'],'测试市大学路2号')
        self.assertEqual(claims['location.postal_code'],'100084')
        self.assertEqual(claims['contacts.phone'],'招生咨询电话: 010-87654321')

    def test_multiple_postcodes_do_not_choose_one_for_all_campuses(self):
        p=page('<footer>甲校区 地址：测试市大学路2号 邮编：100084<br>乙校区 地址：测试市大学路3号 邮编：100085</footer>')
        claims={c['field']:c['value'] for c in contact_claims(p,'homepage')}
        self.assertNotIn('location.postal_code',claims)
        self.assertIn('大学路3号',claims['location.address'])

    def test_saved_ledger_retracts_placeholder_portal_and_incomplete_address(self):
        p=migrate({'visual':{}})
        p['resources']['admissions_url'].update(value='https://www.test.edu.cn/index.htm',source='https://www.test.edu.cn',source_type='official_website',verified='auto',availability='found')
        record=dict(checked_at='2026-10-01',assets=[],claims=[
            dict(field='resources.admissions_url',value='https://www.test.edu.cn/index.htm',source='https://www.test.edu.cn'),
            dict(field='location.address',value='北京市朝阳区',source='https://www.test.edu.cn')])
        apply_record(p,sanitize_record(record))
        self.assertEqual(p['resources']['admissions_url']['availability'],'unresearched')
        self.assertEqual(p['location']['address']['availability'],'unresearched')
        self.assertEqual(len(record['excluded_claims']),2)

    def test_footer_government_and_header_menu_marks_are_not_badges(self):
        p=page('<header class="logo"><img src="school_logo.png"><img src="menu.png"></header>'
               '<footer><img src="footer_sydw.png" alt="事业单位logo"><img src="logo.png"></footer>')
        self.assertEqual([i['src'] for i in p.images],['school_logo.png'])

    def test_embedded_pdf_is_a_static_lead_without_executing_the_player(self):
        p=page('<div pdfsrc="/vi.pdf" swsrc="/vi.swf" sudyfile-attr="code"></div>'
               '<iframe src="/another.pdf"></iframe><script>fetch("/secret")</script>')
        self.assertEqual([d['url'] for d in p.documents],['/vi.pdf','/another.pdf'])

    def test_visual_view_discloses_secondary_color_conflict(self):
        p=migrate({'identity':{'name_zh':'测试大学'},'visual':{
            'color_primary':{'availability':'unresearched'},'vi_url':{'availability':'unresearched'},
            'color_secondary':{'availability':'conflict','note':'RGB与HEX不一致',
                'candidates':[{'value':'#A72126','source':'https://www.test.edu.cn/vi.pdf','basis':'RGB换写'},
                              {'value':'#005375','source':'https://www.test.edu.cn/vi.pdf','basis':'直接印出的HEX'}]}}})
        view=render_visual(p)
        self.assertIn('#A72126',view)
        self.assertIn('#005375',view)
        self.assertIn('RGB与HEX不一致',view)

    def test_portals_require_exact_purpose_label_and_school_host(self):
        p=page('<a href="https://zs.test.edu.cn">本科招生网</a>'
               '<a href="https://other.edu.cn">就业网</a><a href="/news">招生工作研讨会</a>'
               '<a href="/en"><img alt="English" src="lang.png"></a>')
        claims={c['field']:c['value'] for c in portal_claims(p,'https://www.test.edu.cn','https://www.test.edu.cn')}
        self.assertEqual(claims,{'resources.admissions_url':'https://zs.test.edu.cn','resources.english_website':'https://www.test.edu.cn/en'})

    def test_import_preserves_existing_fact_and_never_promotes_sample(self):
        p=migrate({'visual':{'color_primary':{'value':'#123456','availability':'found','verified':'human'}}})
        p['location']['address'].update(value='审定地址',availability='found',verified='human')
        record=dict(checked_at='2026-10-01',claims=[dict(field='location.address',value='自动地址',source='https://www.test.edu.cn',basis='页脚',evidence=['地址'])],
                    assets=[dict(asset_id='x',source='https://www.test.edu.cn',url='https://www.test.edu.cn/logo.png',verified='auto',access_status='content_inspected',colors=['#987654'])])
        apply_record(p,record);apply_record(p,record)
        self.assertEqual(p['location']['address']['value'],'审定地址')
        self.assertEqual(p['visual']['color_primary']['value'],'#123456')
        self.assertEqual(len(p['visual']['logo_assets']),1)
        self.assertEqual(len(p['visual']['color_palette']),1)
        self.assertFalse(p['visual']['color_palette'][0]['official'])


if __name__=='__main__':unittest.main()
