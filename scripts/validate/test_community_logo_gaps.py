import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from collect_community_logo_gaps import LogoPage,page_candidates,retain_attempt_history


def page(extra='',name='测试大学',alt='测试大学校徽'):
    p=LogoPage();p.feed('<h1>'+name+'</h1><img alt="'+alt+'" src="https://cdn.urongda.com/images/normal/medium/test.png"><a href="https://url90.ctfile.com/f/a">测试大学-logo.svg</a>'+extra);return p


class CommunityLogoTests(unittest.TestCase):
    def test_exact_school_name_and_active_named_listing(self):
        images,links=page_candidates(page(),'测试大学')
        self.assertEqual(len(images),1);self.assertEqual(links[0]['format'],'SVG')

    def test_parent_name_and_wrong_image_alt_are_rejected(self):
        for p in [page(name='测试大学独立学院'),page(alt='别校校徽')]:
            with self.assertRaises(ValueError):page_candidates(p,'测试大学')

    def test_renamed_suspended_preview_is_not_imported(self):
        with self.assertRaisesRegex(ValueError,'renamed_or_suspended_logo'):
            page_candidates(page('<p>校徽资源暂停下载，新版官方校徽正在搜集中</p>'),'测试大学')

    def test_source_scripts_are_not_visible_evidence(self):
        images,_=page_candidates(page('<script>校徽资源暂停下载</script>'),'测试大学')
        self.assertEqual(len(images),1)

    def test_failed_retry_keeps_prior_read_data_and_access_history(self):
        old=dict(status='community_logo_read',source='https://example.com',source_sha256='a'*64,
                 assets=[{'sha256':'b'*64}],resources=[{'title':'logo'}],attempts=[{'status':'content_inspected'}])
        new=dict(status='access_or_identity_gap',assets=[],resources=[],attempts=[{'status':'access_gap'}])
        result=retain_attempt_history(new,old)
        self.assertEqual(result['status'],'community_logo_read')
        self.assertEqual(result['last_attempt_status'],'access_or_identity_gap')
        self.assertEqual(result['assets'],old['assets'])
        self.assertEqual(result['previous_attempts'][0]['attempts'],old['attempts'])


if __name__=='__main__':unittest.main()
