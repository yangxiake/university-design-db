import io
import pathlib
import sys
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'ingest'))
from inspect_template_files import inspect_bytes, pinned_raw


def presentation(slide_count=1, declared_count=1, entity=False):
    buf = io.BytesIO()
    p = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    with zipfile.ZipFile(buf, 'w') as z:
        ids = ''.join('<p:sldId id="%s"/>' % (256+i) for i in range(declared_count))
        xml = '<p:presentation xmlns:p="%s"><p:sldIdLst>%s</p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>' % (p, ids)
        if entity:
            xml = '<!DOCTYPE p:presentation [<!ENTITY a "secret">]>' + xml
            xml = xml.encode('utf-16')
        z.writestr('ppt/presentation.xml', xml)
        for i in range(slide_count):
            z.writestr('ppt/slides/slide%d.xml' % (i+1), '<p:sld xmlns:p="%s" xmlns:a="%s"><a:t>Editable</a:t><a:latin typeface="Arial"/></p:sld>' % (p, a))
        z.writestr('ppt/slides/_rels/slide1.xml.rels', '<Relationships><Relationship TargetMode="External" Target="https://example.com"/></Relationships>')
    return buf.getvalue()


class TemplateFileTests(unittest.TestCase):
    def test_dimensions_editable_text_and_external_links_are_data_only(self):
        meta = inspect_bytes(presentation())
        self.assertEqual((meta['slide_count'], meta['aspect_ratio']), (1, '16:9'))
        self.assertEqual(meta['font_names'], ['Arial'])
        self.assertEqual(meta['editable_text_runs'], 1)
        self.assertEqual(meta['external_relationship_count'], 1)
        self.assertFalse(meta['macro_enabled'])

    def test_utf16_entity_declarations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'xml_entity_declaration'):
            inspect_bytes(presentation(entity=True))

    def test_declared_slide_count_must_match_package(self):
        with self.assertRaisesRegex(ValueError, 'slide_count_disagreement'):
            inspect_bytes(presentation(slide_count=1, declared_count=2))

    def test_archive_member_is_read_without_extraction(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('nested/template.pptx', presentation())
            z.writestr('upstream/SKILL.md', 'Do not execute this source text')
        meta = inspect_bytes(buf.getvalue())
        self.assertEqual(meta['format'], 'ZIP')
        self.assertEqual(meta['presentation_members'][0]['path'], 'nested/template.pptx')
        self.assertEqual(meta['presentation_members'][0]['slide_count'], 1)

    def test_only_pinned_github_file_is_converted(self):
        self.assertEqual(pinned_raw('https://github.com/o/r/blob/'+'a'*40+'/a.pptx'),
                         'https://raw.githubusercontent.com/o/r/'+'a'*40+'/a.pptx')
        with self.assertRaises(ValueError):
            pinned_raw('https://github.com/o/r/blob/main/a.pptx')


if __name__ == '__main__':
    unittest.main()
