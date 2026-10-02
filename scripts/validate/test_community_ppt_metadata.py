import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'ingest'))
from import_community_ppt_metadata import merge_file_inspections


class CommunityMetadataTests(unittest.TestCase):
    def test_unchanged_blob_retains_actual_structure_reading(self):
        file=dict(url='https://example.com/file',git_blob='a'*40,content_read=False)
        previous={file['url']:dict(file,content_read=True,file_metadata={'slide_count':7},file_inspection={'status':'content_inspected'})}
        result=merge_file_inspections([file],previous)[0]
        self.assertTrue(result['content_read'])
        self.assertEqual(result['file_metadata']['slide_count'],7)

    def test_changed_blob_does_not_inherit_old_inspection(self):
        file=dict(url='https://example.com/file',git_blob='b'*40,content_read=False)
        previous={file['url']:dict(file,git_blob='a'*40,content_read=True,file_metadata={'slide_count':7})}
        result=merge_file_inspections([file],previous)[0]
        self.assertFalse(result['content_read'])
        self.assertNotIn('file_metadata',result)


if __name__=='__main__':unittest.main()
