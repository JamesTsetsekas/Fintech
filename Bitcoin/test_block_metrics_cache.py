"""Cache-key regressions for the daily block-metrics aggregate."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from Bitcoin import bitcoin_chart_utils as utils

HEADER = "block_height,timestamp,difficulty,size,weight,reward,subsidy,fees,tx_count\n"


def block_rows(first_height, day_epoch, count=2, fees=1000):
    return "".join(
        f"{first_height + i},{day_epoch + i * 600},1000000,1500,4000,{625_000_000 + fees},625000000,{fees},10\n"
        for i in range(count)
    )


class BlockMetricsCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.first = self.dir / "block_data_1.csv"
        self.second = self.dir / "block_data_2.csv"
        self.first.write_text(HEADER + block_rows(1, 1_700_000_000))
        self.second.write_text(HEADER + block_rows(100, 1_700_086_400 * 2, fees=5000))

    def load(self):
        return utils.load_daily_block_metrics(self.dir)

    def count_aggregations(self):
        return patch.object(pd, "concat", wraps=pd.concat)

    def test_unchanged_inputs_reuse_the_cache(self):
        first = self.load()
        with self.count_aggregations() as concat:
            second = self.load()
        concat.assert_not_called()
        self.assertEqual(len(first), len(second))

    def test_deleted_input_invalidates_the_cache(self):
        both = self.load()
        self.second.unlink()
        # The remaining file is *older* than the cache, which the previous
        # mtime-only check treated as still valid.
        remaining = self.load()
        self.assertGreater(len(both), len(remaining))
        self.assertEqual(int(remaining["Block_Count"].sum()), 2)

    def test_added_or_edited_input_invalidates_the_cache(self):
        self.load()
        stat = self.first.stat()
        self.first.write_text(HEADER + block_rows(1, 1_700_000_000, count=3))
        # Restore the original mtime: size alone must still invalidate.
        os.utime(self.first, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(int(self.load()["Block_Count"].sum()), 5)

    def test_code_version_bump_invalidates_the_cache(self):
        self.load()
        with patch.object(utils, "BLOCK_METRICS_CACHE_VERSION", utils.BLOCK_METRICS_CACHE_VERSION + 1), \
                self.count_aggregations() as concat:
            self.load()
        concat.assert_called()

    def test_corrupt_cache_or_key_is_rebuilt(self):
        expected = self.load()
        for name, content in (
            ("daily_block_metrics_cache.csv", "\x00not,a\nvalid cache"),
            ("daily_block_metrics_cache.csv", "Date\n2024-01-01\n"),
            ("daily_block_metrics_cache.key.json", "{truncated"),
        ):
            with self.subTest(name=name, content=content[:10]):
                (self.dir / name).write_text(content)
                with self.count_aggregations() as concat:
                    rebuilt = self.load()
                concat.assert_called()
                self.assertEqual(len(rebuilt), len(expected))
                # The rebuild repairs the cache so the next call can reuse it.
                with self.count_aggregations() as concat:
                    self.load()
                concat.assert_not_called()

    def test_missing_key_file_forces_rebuild(self):
        self.load()
        (self.dir / "daily_block_metrics_cache.key.json").unlink()
        with self.count_aggregations() as concat:
            self.load()
        concat.assert_called()


if __name__ == "__main__":
    unittest.main()
