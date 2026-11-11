"""Publish fingerprinting and the publish-pending marker. Fully offline."""

import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publish_pending as pending

with patch("dotenv.load_dotenv"):
    _spec = importlib.util.spec_from_file_location("fintech_runner_publish", Path(__file__).with_name("run.py"))
    runner = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(runner)


def stage(directory: Path, *, generated_at, updated_at, value=1.0, extra=None):
    (directory / "web/data/bitcoin").mkdir(parents=True)
    (directory / "index.html").write_text("<html></html>", encoding="utf-8")
    chart = {
        "id": "demo",
        "updated_at": updated_at,
        "series": [{"x": ["2026-01-01"], "y": [value]}],
        "nested": [{"generated_at": generated_at, "keep": 1}],
    }
    chart.update(extra or {})
    (directory / "web/data/bitcoin/demo.json").write_text(json.dumps(chart), encoding="utf-8")
    manifest = {"generated_at": generated_at, "charts": ["demo"]}
    (directory / "web/data/site-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


class FingerprintTests(unittest.TestCase):
    def fingerprint(self, branch="gh-pages", **kwargs):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            stage(site, **kwargs)
            return runner.static_site_fingerprint(site, branch)

    def test_sites_differing_only_in_timestamps_hash_equal(self):
        first = self.fingerprint(generated_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00+00:00")
        second = self.fingerprint(generated_at="2026-02-02T12:34:56Z", updated_at="2030-05-05T05:05:05+00:00")
        self.assertEqual(first, second)

    def test_real_data_change_hashes_differently(self):
        base = dict(generated_at="g", updated_at="u")
        self.assertNotEqual(self.fingerprint(**base, value=1.0), self.fingerprint(**base, value=2.0))
        self.assertNotEqual(self.fingerprint(**base), self.fingerprint(**base, extra={"title": "renamed"}))

    def test_non_volatile_fields_with_similar_names_still_count(self):
        base = dict(generated_at="g", updated_at="u")
        self.assertNotEqual(
            self.fingerprint(**base, extra={"checked_at": "a"}), self.fingerprint(**base, extra={"checked_at": "b"})
        )

    def test_target_branch_is_part_of_the_fingerprint(self):
        base = dict(generated_at="g", updated_at="u")
        self.assertNotEqual(self.fingerprint("gh-pages", **base), self.fingerprint("preview", **base))

    def test_publish_skips_when_only_timestamps_changed(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "publish-state.json"
            fingerprints = []

            def stage_site(site):
                stage(site, generated_at=f"g{len(fingerprints)}", updated_at=f"u{len(fingerprints)}")
                fingerprints.append(1)

            def publish():
                with patch.object(runner, "get_current_branch", return_value="main"), \
                        patch.object(runner, "stage_static_site", side_effect=stage_site), \
                        patch.object(runner, "PUBLISH_STATE_PATH", state), \
                        patch.dict(os.environ, {"ALLOW_UNCOMMITTED_SITE_PUBLISH": "1"}), \
                        patch.object(runner.subprocess, "run") as run_git, \
                        redirect_stdout(io.StringIO()) as output:
                    run_git.return_value.returncode = 0
                    run_git.return_value.stdout = "https://github.com/example/sentinel.git\n"
                    run_git.return_value.stderr = ""
                    return runner.publish_static_site(), output.getvalue()

            self.assertTrue(publish()[0])  # first publish pushes (mocked) and records fingerprint
            self.assertTrue(state.exists())
            ok, output = publish()
            self.assertTrue(ok)
            self.assertIn("unchanged", output)


class PublishPendingTests(unittest.TestCase):
    def test_without_marker_only_six_hour_windows_publish(self):
        for hour in range(24):
            should, reason = pending.publish_decision(hour, "abc", {})
            self.assertEqual(should, hour % 6 == 0, hour)
        self.assertEqual(pending.publish_decision(6, "abc", {}), (True, "scheduled-window"))

    def test_failed_last_publish_is_retried_next_hour(self):
        self.assertEqual(
            pending.publish_decision(7, "abc", {"status": "failed", "source_head": "abc"}),
            (True, "retry-failed-publish"),
        )

    def test_source_head_change_since_last_success_publishes(self):
        marker = {"status": "success", "source_head": "abc"}
        self.assertEqual(pending.publish_decision(7, "def", marker), (True, "source-changed"))
        self.assertEqual(pending.publish_decision(7, "abc", marker), (False, "deferred"))
        self.assertEqual(pending.publish_decision(7, None, marker), (False, "deferred"))

    def test_garbage_marker_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "m.json"
            for content in ("{nope", "[]", '"x"', ""):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(pending.read_marker(path), {})
            self.assertEqual(pending.read_marker(path.with_name("missing.json")), {})

    def test_record_attempt_round_trip_keeps_last_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "logs" / "publish-pending.json"
            moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
            pending.record_attempt("aaa", True, path, now=moment)
            self.assertEqual(pending.read_marker(path)["status"], "success")
            pending.record_attempt("bbb", False, path, now=moment)
            marker = pending.read_marker(path)
            self.assertEqual(
                (marker["status"], marker["source_head"], marker["last_success_head"]), ("failed", "bbb", "aaa")
            )
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_cli_prints_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "m.json"
            pending.record_attempt("aaa", False, marker)
            output = io.StringIO()
            with redirect_stdout(output):
                pending.main(["decide", "--hour", "7", "--head", "aaa", "--marker", str(marker)])
            self.assertEqual(output.getvalue().strip(), "publish retry-failed-publish")
            output = io.StringIO()
            with redirect_stdout(output):
                pending.main(["decide", "--hour", "7", "--head", "aaa", "--marker", str(marker.with_name("x.json"))])
            self.assertEqual(output.getvalue().strip(), "defer deferred")


class PublishRecordingTests(unittest.TestCase):
    def run_publish(self, outcome):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "publish-pending.json"
            with patch.object(runner, "PUBLISH_PENDING_PATH", marker), \
                    patch.object(runner, "get_source_head", return_value="headsha"), \
                    patch.object(runner, "publish_static_site",
                                 side_effect=outcome if isinstance(outcome, BaseException) else None,
                                 return_value=outcome if not isinstance(outcome, BaseException) else None):
                try:
                    result = runner.publish_and_record()
                except BaseException as error:  # noqa: BLE001 - assert recorded state for interrupts too
                    result = type(error).__name__
                return result, pending.read_marker(marker)

    def test_success_failure_and_exception_are_recorded(self):
        result, marker = self.run_publish(True)
        self.assertEqual((result, marker["status"], marker["source_head"]), (True, "success", "headsha"))
        result, marker = self.run_publish(False)
        self.assertEqual((result, marker["status"]), (False, "failed"))
        result, marker = self.run_publish(RuntimeError("boom"))
        self.assertEqual((result, marker["status"]), ("RuntimeError", "failed"))

    def test_shell_wrapper_uses_the_helper_and_keeps_six_hour_fallback(self):
        script = Path(__file__).with_name("run_cron.sh").read_text(encoding="utf-8")
        self.assertIn("publish_pending.py", script)
        self.assertIn("% 6 == 0", script)


if __name__ == "__main__":
    unittest.main()
