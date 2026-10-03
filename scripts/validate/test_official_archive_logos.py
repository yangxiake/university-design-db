"""Archive graphics need bounded bytes, safe members and school decisions."""
import hashlib
import io
import pathlib
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
import collect_official_archive_logos as importer


class OfficialArchiveLogoTests(unittest.TestCase):
    def test_hash_and_member_paths_are_verified_without_extracting_names(self):
        png=io.BytesIO();Image.new('RGB',(20,20),'red').save(png,format='PNG')
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('../escape.png',png.getvalue())
            z.writestr('safe/logo.png',png.getvalue())
        body=archive.getvalue()
        receipt=dict(school_code='1',name_zh='测试大学',url='https://test.edu.cn/logo.zip',checked_at='2026-10-02',file_metadata={'sha256':hashlib.sha256(body).hexdigest()})
        with tempfile.TemporaryDirectory() as directory, patch.object(importer,'ROOT',pathlib.Path(directory)):
            rows=importer.inspect_members(receipt,body)
            self.assertEqual([r['archive_member'] for r in rows],['safe/logo.png'])
            self.assertFalse((pathlib.Path(directory)/'safe').exists())
            with self.assertRaisesRegex(ValueError,'hash_mismatch'):
                importer.inspect_members(receipt,body+b'changed')

    def test_parser_success_cannot_override_school_identity(self):
        row=dict(status='image_content_read',name_zh='测试大学',archive_url='https://test.edu.cn/logo.zip')
        identity=dict(name_zh='测试大学',official_website={'value':'https://test.edu.cn/'})
        decision=dict(name_zh='旧学校',kind='badge',basis='已查看')
        with self.assertRaisesRegex(ValueError,'identity_not_confirmed'):
            importer.reviewed_entry(row,decision,identity)


if __name__=='__main__':
    unittest.main()
