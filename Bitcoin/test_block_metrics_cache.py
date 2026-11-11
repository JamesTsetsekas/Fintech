"""The derived daily block-metrics cache must follow its source files and code version."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Bitcoin import bitcoin_chart_utils as utils

HEADER = "block_height,timestamp,difficulty,size,weight,reward,subsidy,fees,tx_count\n"


def write_blocks(path: Path, heights, day_offset=0):
    rows = "".join(
        f"{height},{1767225600 + (day_offset + index) * 86400},1000,100,400,625000000,625000000,1000,2\n"
        for index, height in enumerate(heights)
    )
    path.write_text(HEADER + rows, encoding="utf-8")


class BlockMetricsCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        write_blocks(self.dir / "block_data_1.csv", [1, 2], 0)
        write_blocks(self.dir / "block_data_2.csv", [3, 4], 5)
        self.cache = self.dir / utils.BLOCK_METRICS_CACHE_NAME
        self.meta = self.dir / utils.BLOCK_METRICS_CACHE_META_NAME

    def blocks(self):
        return int(utils.load_daily_block_metrics(self.dir)["Block_Count"].sum())

    def test_unchanged_sources_reuse_the_cache(self):
        self.assertEqual(self.blocks(), 4)
        with patch.object(utils.pd, "concat", side_effect=AssertionError("recomputed")):
            self.assertEqual(self.blocks(), 4)

    def test_deleting_a_source_invalidates_the_cache_even_though_remaining_files_are_older(self):
        self.assertEqual(self.blocks(), 4)
        (self.dir / "block_data_2.csv").unlink()
        self.assertEqual(self.blocks(), 2)

    def test_adding_a_source_invalidates_the_cache_even_with_an_old_mtime(self):
        self.assertEqual(self.blocks(), 4)
        added = self.dir / "block_data_3.csv"
        write_blocks(added, [5, 6, 7], 10)
        os.utime(added, (1_000_000, 1_000_000))  # older than the cache
        self.assertEqual(self.blocks(), 7)

    def test_replacing_a_source_with_same_size_and_older_mtime_invalidates(self):
        self.assertEqual(self.blocks(), 4)
        path = self.dir / "block_data_2.csv"
        before = path.stat()
        write_blocks(path, [3, 4], 6)  # same size, different content
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns - 5_000_000_000))
        self.assertEqual(path.stat().st_size, before.st_size)
        days = set(utils.load_daily_block_metrics(self.dir)["Date"].dt.day)
        self.assertIn(8, days)  # new day from the rewritten file

    def test_version_bump_invalidates_the_cache(self):
        self.assertEqual(self.blocks(), 4)
        with patch.object(utils, "BLOCK_METRICS_CACHE_VERSION", utils.BLOCK_METRICS_CACHE_VERSION + 1), \
                patch.object(utils.pd, "concat", wraps=utils.pd.concat) as concat:
            self.assertEqual(self.blocks(), 4)
            self.assertTrue(concat.called)

    def test_legacy_cache_without_metadata_is_rebuilt(self):
        self.assertEqual(self.blocks(), 4)
        self.meta.unlink()
        self.cache.write_text("Date,Fees_BTC\n2026-01-01,1\n", encoding="utf-8")
        self.assertEqual(self.blocks(), 4)

    def test_corrupt_cache_or_metadata_is_rebuilt(self):
        for target, payload in (
            ("cache", b"\x00\xff not,a,csv\n\"unterminated"),
            ("cache", b""),
            ("cache", b"Date,Fees_BTC\n2026-01-01,1\n"),  # valid CSV, missing columns
            ("meta", b"{not json"),
            ("meta", b"[]"),
        ):
            with self.subTest(target=target, payload=payload[:12]):
                self.assertEqual(self.blocks(), 4)
                (self.cache if target == "cache" else self.meta).write_bytes(payload)
                self.assertEqual(self.blocks(), 4)
                # ...and the cache is healthy again afterwards.
                with patch.object(utils.pd, "concat", side_effect=AssertionError("recomputed")):
                    self.assertEqual(self.blocks(), 4)

    def test_no_sources_returns_empty_frame_with_expected_columns(self):
        for path in self.dir.glob("block_data_*.csv"):
            path.unlink()
        frame = utils.load_daily_block_metrics(self.dir)
        self.assertTrue(frame.empty)
        self.assertEqual(list(frame.columns), utils.BLOCK_METRICS_COLUMNS)


if __name__ == "__main__":
    unittest.main()
