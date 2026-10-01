"""Check source preservation, unsafe literals and visual-content interpretation."""
import copy
import io
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from static_js_data import extract_assignment, extract_universities
from profile_extensions import migrate, put_fact, rgb, upsert
from expand_repository_fields import inspect_bytes,assessment_entries,seed_palettes,upsert_asset
from validate_profiles import check_extended_entry, check_fact


class EnrichedFieldsTests(unittest.TestCase):
    def test_only_static_javascript_data_is_read(self):
        self.assertEqual(extract_universities("/* comment */ window.UNIVERSITIES.push({name:'甲',tags:['A'],year:2021,});"),[{'name':'甲','tags':['A'],'year':2021}])
        for text in ["window.UNIVERSITIES = [fetch('https://example.org')];",
                     "window.UNIVERSITIES = []; process.exit();",
                     "window.LOGOS = {x:(()=>42)()};"]:
            with self.assertRaises(ValueError):
                (extract_assignment(text,'LOGOS') if 'LOGOS' in text else extract_universities(text))

    def test_duplicate_literal_keys_are_rejected(self):
        with self.assertRaises(ValueError):extract_assignment("window.LOGOS = {x:1,x:2};",'LOGOS')

    def test_schema_migration_keeps_existing_fields(self):
        original={'schema_version':2,'identity':{'school_code':'123','name_zh':'甲','name_en':{'value':'Existing'}},'visual':{'color_primary':{'value':'#123456'}}}
        profile=migrate(copy.deepcopy(original))
        self.assertEqual(profile['identity']['name_en'],original['identity']['name_en'])
        self.assertEqual(profile['visual']['color_primary'],original['visual']['color_primary'])
        self.assertEqual(migrate(copy.deepcopy(profile)),profile)

    def test_source_upsert_is_idempotent_and_keeps_human_choice(self):
        items=[dict(asset_id='a',verified='human',title='Reviewed')]
        self.assertFalse(upsert(items,dict(asset_id='a',verified='auto',title='New'),lambda x:x['asset_id']))
        self.assertEqual(items[0]['title'],'Reviewed')
        self.assertTrue(upsert(items,dict(asset_id='b',verified='auto'),lambda x:x['asset_id']))
        self.assertFalse(upsert(items,dict(asset_id='b',verified='auto'),lambda x:x['asset_id']))
        self.assertEqual(len(items),2)
        profile={'visual':{'logo_assets':[dict(asset_id='c',commit='a'*40,access_status='content_inspected',format='jpeg',width=12,sha256='b'*64)]}}
        upsert_asset(profile,dict(asset_id='c',commit='a'*40,access_status='indexed_not_fetched',format='svg'))
        self.assertEqual(profile['visual']['logo_assets'][0]['access_status'],'content_inspected')
        self.assertEqual(profile['visual']['logo_assets'][0]['format'],'jpeg')
        self.assertEqual(profile['visual']['logo_assets'][0]['sha256'],'b'*64)

    def test_image_format_comes_from_content(self):
        from PIL import Image
        handle=io.BytesIO();Image.new('RGB',(12,8),(50,70,180)).save(handle,format='JPEG')
        metadata=inspect_bytes(handle.getvalue(),'incorrect.svg')
        self.assertEqual(metadata['format'],'jpeg')
        self.assertFalse(metadata['vector'])
        self.assertEqual((metadata['width'],metadata['height']),(12,8))

    def test_svg_active_content_is_rejected(self):
        for body in [b'<svg><script>alert(1)</script></svg>',b'<svg onload="test()"/>',b'<svg><image href="https://example.org/x.png"/></svg>']:
            with self.assertRaises(ValueError):inspect_bytes(body,'badge.svg')

    def test_svg_with_embedded_pixels_is_not_pure_vector(self):
        import base64
        from PIL import Image
        handle=io.BytesIO();Image.new('RGB',(8,8),(30,70,180)).save(handle,format='PNG')
        body=b'<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,'+base64.b64encode(handle.getvalue())+b'"/></svg>'
        metadata=inspect_bytes(body,'badge.svg')
        self.assertEqual(metadata['representation'],'svg_with_raster')
        self.assertFalse(metadata['vector'])
        self.assertTrue(metadata['colors'])

    def test_community_palette_cannot_become_official(self):
        item=dict(value='#123456',rgb=rgb('#123456'),method='community_theme',official=True,
                  basis='theme source',role='reference',source='https://example.org/theme',verified='auto',checked_at='2026-10-01')
        errors=[];check_extended_entry('visual.color_palette',item,'test',errors)
        self.assertTrue(any('official flag' in error for error in errors))
        item['official']=False;item['rgb']=[1,2,3]
        errors=[];check_extended_entry('visual.color_palette',item,'test',errors)
        self.assertTrue(any('RGB does not match HEX' in error for error in errors))

    def test_admission_data_requires_temporal_and_regional_basis(self):
        errors=[];check_extended_entry('admissions.cutoffs',dict(source='https://example.org/data',checked_at='2026-10-01',verified='auto',minimum_score=600),'test',errors)
        self.assertTrue(any('year required' in error for error in errors))
        self.assertTrue(any('missing region' in error for error in errors))

    def test_inconsistent_grades_preserve_both_without_choosing(self):
        entries=assessment_entries(dict(aplus=['地理学'],a=['地理学']),dict(source='https://example.org/record'))
        self.assertEqual(entries[0]['availability'],'conflict')
        self.assertIsNone(entries[0]['grade'])
        self.assertEqual({c['grade'] for c in entries[0]['candidates']},{'A+','A'})

    def test_existing_theme_colors_project_as_community_references(self):
        profile=migrate(dict(visual=dict(color_primary={'availability':'unresearched'},color_secondary={'availability':'unresearched'}),
                             resources=dict(community_resources=[dict(source='https://example.org/theme',publisher='author',commit='a'*40,
                                palette=[dict(value='#123456',basis='theme source')])])) )
        seed_palettes(profile)
        self.assertEqual(profile['visual']['color_palette'][0]['method'],'community_theme')
        self.assertFalse(profile['visual']['color_palette'][0]['official'])

    def test_legacy_svg_encodings_and_namespace_aliases_are_read_as_data(self):
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8"><path fill="#123456"/></svg>'
        self.assertEqual(inspect_bytes(svg.encode('utf-16'),'legacy.svg')['format'],'svg')
        body=b'<!DOCTYPE svg [<!ENTITY ns_ai "http://ns.adobe.com/AdobeIllustrator/10.0/">]><svg xmlns="http://www.w3.org/2000/svg" xmlns:i="&ns_ai;"><path fill="#123456"/></svg>'
        self.assertTrue(inspect_bytes(body,'legacy.svg')['vector'])
        unsafe=b'<!DOCTYPE svg [<!ENTITY ns_ai SYSTEM "file:///etc/passwd">]><svg/>'
        with self.assertRaises(ValueError):inspect_bytes(unsafe,'unsafe.svg')


if __name__=='__main__':unittest.main()
