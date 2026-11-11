import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from Bitcoin import run_all_reports as runner


class ReportRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = self.root / 'data' / 'bitcoin_csv_data'
        data.mkdir(parents=True)
        self.csv = data / 'daily_price.csv'
        self.csv.write_text('old')
        script = self.root / 'example' / 'example.py'
        script.parent.mkdir()
        script.write_text('# report')
        self.report = dict(name='Example', path=script, output='example.png')
        self.output = script.parent / 'example.png'
        self.output.write_text('old chart')
        self.args = Namespace(list=False, only=[], skip_update=False)
        for name, value in [('script_dir', self.root), ('REPORTS', [self.report])]:
            p = patch.object(runner, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict('os.environ', {}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def invoke(self, changed=False, success=True):
        def generate(report):
            if success:
                self.output.write_text('new chart')
            return success
        with patch.object(runner, 'parse_args', return_value=self.args), \
             patch.object(runner, 'update_data', return_value=changed), \
             patch.object(runner, 'run_report', side_effect=generate) as reports, \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as exit:
            runner.main()
        return exit.exception.code, reports.call_count

    def test_retry_after_updater_committed_data_and_generation_failed(self):
        self.csv.write_text('new')
        self.assertEqual(self.invoke(changed=True, success=False), (1, 1))
        self.assertEqual(self.invoke(changed=False), (0, 1))
        self.assertEqual(self.invoke(changed=False), (0, 0))


    def test_inputs_code_and_missing_outputs_require_regeneration(self):
        self.assertEqual(self.invoke(), (0, 1))
        for path in [self.csv, self.report['path'], self.root / 'bitcoin_chart_utils.py']:
            path.write_text('changed content')
            self.assertEqual(self.invoke(), (0, 1))
            self.assertEqual(self.invoke(), (0, 0))
        self.output.unlink()
        self.assertEqual(self.invoke(), (0, 1))
        self.output.write_text('')
        self.assertEqual(self.invoke(), (0, 1))

    def test_manual_runs_do_not_bless_scheduled_outputs(self):
        for only, skip in [(['Example'], False), ([], True)]:
            self.args.only, self.args.skip_update = [], False
            self.assertEqual(self.invoke(), (0, 1))
            self.args.only, self.args.skip_update = only, skip
            self.assertEqual(self.invoke(), (0, 1))
            self.assertFalse((self.root / '.successful_generation').exists())
            self.args.only, self.args.skip_update = [], False
            self.assertEqual(self.invoke(), (0, 1))
            (self.root / '.successful_generation').unlink()

    def test_failed_refresh_does_not_run_reports(self):
        self.assertEqual(self.invoke(changed=None), (1, 0))

    def test_failed_generation_invalidates_previous_success(self):
        self.assertEqual(self.invoke(), (0, 1))
        self.assertEqual(self.invoke(changed=True, success=False), (1, 1))
        self.assertFalse((self.root / '.successful_generation').exists())
        self.assertEqual(self.invoke(), (0, 1))

    def test_missing_output_cannot_write_marker(self):
        self.output.unlink()
        with patch.object(self.output.__class__, 'write_text', return_value=0):
            self.assertEqual(self.invoke(), (1, 1))
        self.assertFalse((self.root / '.successful_generation').exists())

    def test_corrupt_marker_and_selection_change_require_generation(self):
        (self.root / '.successful_generation').write_bytes(b'\xff')
        self.assertEqual(self.invoke(), (0, 1))
        self.report['output'] = 'renamed.png'
        self.output = self.report['path'].parent / 'renamed.png'
        self.assertEqual(self.invoke(), (0, 1))

    def test_derived_cache_does_not_trigger_generation(self):
        self.assertEqual(self.invoke(), (0, 1))
        (self.csv.parent / 'daily_block_metrics_cache.csv').write_text('cache')
        self.assertEqual(self.invoke(), (0, 0))


    def test_inputs_changed_during_generation_require_retry(self):
        original = runner.generation_fingerprint
        calls = 0
        def fingerprint(reports):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.csv.write_text('changed while reports ran')
            return original(reports)
        with patch.object(runner, 'generation_fingerprint', side_effect=fingerprint):
            self.assertEqual(self.invoke(), (1, 1))
        self.assertFalse((self.root / '.successful_generation').exists())
        self.assertEqual(self.invoke(), (0, 1))

    def test_marker_replace_failure_never_leaves_success(self):
        marker = self.root / '.successful_generation'
        with patch.object(runner.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                runner.write_generation_marker(marker, 'fingerprint')
        self.assertFalse(marker.exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['data', 'example'])


if __name__ == '__main__':
    unittest.main()
