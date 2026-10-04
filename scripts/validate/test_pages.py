"""Deployment routing and boundaries must hold without copying the whole repository."""
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_pages', ROOT / 'scripts/build_pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)
REVISION = 'a' * 40


class PagesTests(unittest.TestCase):
    def test_only_viewer_inputs_are_published_and_repository_links_pin_the_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / 'viewer').mkdir()
            for name in pages.VIEWER_FILES:
                shutil.copyfile(ROOT / 'viewer' / name, root / 'viewer' / name)
            shutil.copytree(ROOT / 'viewer/data', root / 'viewer/data')
            (root / 'viewer/debug.env').write_text('private placeholder')
            (root / 'viewer/test-image.png').write_bytes(b'image placeholder')
            (root / 'tmp/viewer-previews').mkdir(parents=True)
            (root / 'tmp/viewer-previews/private.png').write_bytes(b'local image')
            output = root / 'tmp/site'
            result = pages.build(root, output, REVISION)
            names = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
            expected = set(pages.VIEWER_FILES) | {'data/catalog.json', '.nojekyll', 'deployment.json'}
            expected |= {'data/provinces/' + p.name for p in (ROOT / 'viewer/data/provinces').glob('*.json')}
            self.assertEqual(names, expected)
            self.assertEqual(result['files'], 40)
            html = (output / 'index.html').read_text()
            self.assertIn('name="repository-base" content="' + pages.REPOSITORY + '/blob/' + REVISION + '/', html)
            self.assertNotIn('href="../', html)
            self.assertEqual(json.loads((output / 'deployment.json').read_text())['source_commit'], REVISION)

    def test_existing_outputs_and_directories_outside_tmp_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            output = root / 'tmp/site'
            output.mkdir(parents=True)
            marker = output / 'existing.txt'
            marker.write_text('keep me')
            with self.assertRaisesRegex(ValueError, 'Output must be empty'):
                pages.build(root, output, REVISION)
            self.assertEqual(marker.read_text(), 'keep me')
            with self.assertRaisesRegex(ValueError, 'inside tmp'):
                pages.build(root, root / 'viewer', REVISION)
            self.assertFalse((root / 'viewer').exists())

    def test_traversal_and_symbolic_sources_cannot_publish_unrelated_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / 'viewer/data').mkdir(parents=True)
            catalog = json.loads((ROOT / 'viewer/data/catalog.json').read_text())
            catalog['provinces'][0] = '../private'
            (root / 'viewer/data/catalog.json').write_text(json.dumps(catalog))
            with self.assertRaisesRegex(ValueError, 'Invalid regional bundle path'):
                pages.build(root, root / 'tmp/site', REVISION)
            (root / 'viewer/data/catalog.json').write_bytes((ROOT / 'viewer/data/catalog.json').read_bytes())
            (root / 'viewer/index.html').write_bytes((ROOT / 'viewer/index.html').read_bytes())
            secret = root / 'private.txt'
            secret.write_text('private placeholder')
            (root / 'viewer/app.mjs').symlink_to(secret)
            with self.assertRaisesRegex(ValueError, 'Source must not be a symbolic link'):
                pages.build(root, root / 'tmp/site', REVISION)
            self.assertFalse((root / 'tmp/site').exists())


if __name__ == '__main__':
    unittest.main()
