"""Local preview files must be verified images, never distributed or fetched."""
import base64
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_viewer_previews', ROOT / 'scripts/prepare_viewer_previews.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class ViewerPreviewTests(unittest.TestCase):
    def test_svg_active_content_and_external_dependencies_are_rejected(self):
        self.assertTrue(preview.safe_image(b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="url(#a)"/></svg>', 'svg'))
        for raw in [b'<svg><script>x</script></svg>', b'<svg onload="x"/>', b'<svg><foreignObject/></svg>',
                    b'<svg><image href="https://example.org/a.png"/></svg>',
                    b'<svg><style>@import "x";</style></svg>', b'<!DOCTYPE svg><svg/>']:
            self.assertFalse(preview.safe_image(raw, 'svg'))

    def test_hash_mismatch_or_unknown_content_cannot_enter_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder); (root / 'indexes').mkdir(); (root / 'tmp/raw').mkdir(parents=True)
            sha = hashlib.sha256(PNG).hexdigest()
            assets = [dict(access_status='content_inspected', format='png', sha256=sha),
                      dict(access_status='content_inspected', format='png', sha256='a' * 64)]
            (root / 'indexes/ppt-profiles.jsonl').write_text(json.dumps(dict(logos=dict(candidates=assets))) + '\n')
            (root / 'tmp/raw/random-name.bin').write_bytes(PNG)
            result = preview.prepare(root)
            self.assertEqual(result['preview_files'], 1)
            manifest = json.loads((root / 'tmp/viewer-previews/index.json').read_text())
            self.assertEqual(set(manifest['files']), {sha})
            self.assertEqual((root / ('tmp/viewer-previews/' + sha + '.png')).read_bytes(), PNG)

    def test_archive_cache_verifies_container_and_member_without_extracting_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder); (root / 'indexes').mkdir(); (root / 'tmp/raw').mkdir(parents=True)
            archive = root / 'tmp/raw/collection.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('../logo.png', PNG)
            sha = hashlib.sha256(PNG).hexdigest(); container = hashlib.sha256(archive.read_bytes()).hexdigest()
            asset = dict(access_status='content_inspected', format='png', sha256=sha,
                         download_kind='archive_member', archive_sha256=container, archive_member='../logo.png')
            (root / 'indexes/ppt-profiles.jsonl').write_text(json.dumps(dict(logos=dict(candidates=[asset]))) + '\n')
            self.assertEqual(preview.prepare(root)['preview_files'], 1)
            self.assertFalse((root / 'logo.png').exists())
            self.assertTrue((root / ('tmp/viewer-previews/' + sha + '.png')).is_file())

    def test_unread_files_and_pdf_pages_are_not_advertised_as_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder); (root / 'indexes').mkdir(); (root / 'tmp/raw').mkdir(parents=True)
            sha = hashlib.sha256(PNG).hexdigest(); (root / 'tmp/raw/a.png').write_bytes(PNG)
            assets = [dict(access_status='indexed_not_fetched', format='png', sha256=sha),
                      dict(access_status='content_inspected', format='png', sha256=sha, download_kind='document_page')]
            (root / 'indexes/ppt-profiles.jsonl').write_text(json.dumps(dict(logos=dict(candidates=assets))) + '\n')
            self.assertEqual(preview.prepare(root)['preview_files'], 0)


if __name__ == '__main__':
    unittest.main()
