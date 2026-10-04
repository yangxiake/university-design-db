"""A successful check must cover the exact source commit before website publishing."""
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('publish_pages', ROOT / 'scripts/publish_pages.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
sys.path.pop(0)


class PagesPublishingTests(unittest.TestCase):
    def test_successful_checks_for_another_commit_cannot_authorize_publication(self):
        self.assertFalse(publisher.quality_passed([
            dict(headSha='old', status='completed', conclusion='success')], 'new'))

    def test_pending_failed_or_canceled_checks_cannot_authorize_publication(self):
        for status, conclusion in [('in_progress', 'success'), ('queued', ''),
                                   ('completed', 'failure'), ('completed', 'cancelled')]:
            self.assertFalse(publisher.quality_passed([
                dict(headSha='current', status=status, conclusion=conclusion)], 'current'))

    def test_completed_successful_check_of_the_exact_commit_allows_publication(self):
        self.assertTrue(publisher.quality_passed([
            dict(headSha='current', status='completed', conclusion='success')], 'current'))


if __name__ == '__main__':
    unittest.main()
