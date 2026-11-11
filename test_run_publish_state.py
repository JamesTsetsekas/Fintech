"""Publish fingerprint and publish-pending regressions (offline, no git remote)."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    spec = importlib.util.spec_from_file_location('fintech_runner_state', Path(__file__).with_name('run.py'))
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)


def stage(site, *, generated_at, updated_at, last_value=3, extra=None):
    (site / 'web' / 'data').mkdir(parents=True, exist_ok=True)
    (site / 'index.html').write_text('<html>site</html>', encoding='utf-8')
    manifest = {'generated_at': generated_at, 'charts': [{'id': 'a'}]}
    chart = {'id': 'a', 'updated_at': updated_at, 'series': [{'x': ['2026-01-01'], 'y': [1, 2, last_value]}]}
    chart.update(extra or {})
    (site / 'web' / 'data' / 'site-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Differently formatted JSON must not matter either.
    (site / 'web' / 'data' / 'a.json').write_text(json.dumps(chart), encoding='utf-8')


class FingerprintTests(unittest.TestCase):
    def fingerprint(self, branch='gh-pages', **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            stage(site, **kwargs)
            return runner.static_site_fingerprint(site, branch)

    def test_timestamp_only_differences_hash_equal(self):
        first = self.fingerprint(generated_at='2026-01-01T00:00:00+00:00', updated_at='2026-01-01T00:00:00+00:00')
        second = self.fingerprint(generated_at='2026-01-01T06:00:00+00:00', updated_at='2026-01-01T06:00:00+00:00')
        self.assertEqual(first, second)

    def test_real_data_change_hashes_differently(self):
        stamp = '2026-01-01T00:00:00+00:00'
        base = self.fingerprint(generated_at=stamp, updated_at=stamp)
        self.assertNotEqual(base, self.fingerprint(generated_at=stamp, updated_at=stamp, last_value=4))
        self.assertNotEqual(base, self.fingerprint(generated_at=stamp, updated_at=stamp, extra={'title': 'new'}))

    def test_target_branch_is_part_of_the_fingerprint(self):
        stamp = '2026-01-01'
        self.assertNotEqual(
            self.fingerprint('gh-pages', generated_at=stamp, updated_at=stamp),
            self.fingerprint('pages-staging', generated_at=stamp, updated_at=stamp),
        )


class PublishPendingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(runner, 'PUBLISH_STATE_PATH', Path(self.temp.name) / 'logs' / 'publish-state.json')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_never_published_is_due(self):
        self.assertTrue(runner.publish_is_due('abc'))

    def test_not_due_until_head_changes(self):
        runner.remember_published_fingerprint('fp', 'gh-pages', 'abc')
        self.assertEqual(runner.last_published_fingerprint(), 'fp')
        self.assertFalse(runner.publish_is_due('abc'))
        self.assertTrue(runner.publish_is_due('def'))

    def test_failed_attempt_is_retried_until_success(self):
        runner.remember_published_fingerprint('fp', 'gh-pages', 'abc')
        runner.mark_publish_pending('abc')
        self.assertTrue(runner.publish_is_due('abc'))
        self.assertEqual(runner.last_published_fingerprint(), 'fp')
        runner.remember_published_fingerprint('fp2', 'gh-pages', 'abc')
        self.assertFalse(runner.publish_is_due('abc'))

    def test_corrupt_state_counts_as_due(self):
        runner.PUBLISH_STATE_PATH.parent.mkdir(parents=True)
        runner.PUBLISH_STATE_PATH.write_text('{broken', encoding='utf-8')
        self.assertTrue(runner.publish_is_due('abc'))
        self.assertIsNone(runner.last_published_fingerprint())

    def test_unknown_head_does_not_force_publish(self):
        runner.remember_published_fingerprint('fp', 'gh-pages', 'abc')
        with patch.object(runner, 'get_head_sha', return_value=None):
            self.assertFalse(runner.publish_is_due())


if __name__ == '__main__':
    unittest.main()
