from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from kelma.kelma_sync_v2.conflict_policy import modified_timestamp, newest_side


class ConflictPolicyTest(unittest.TestCase):
    def test_server_source_time_wins(self) -> None:
        local = {"modified_at": "2026-07-14T10:00:00Z"}
        server = {
            "client_modified_at": "2026-07-14T11:00:00Z",
            "modified_at": "2026-07-14T12:00:00Z",
        }
        self.assertEqual(newest_side(local, server), "server")

    def test_client_time_is_preferred_over_server_receipt_time(self) -> None:
        local = {"modified_at": "2026-07-14T11:00:00Z"}
        server = {
            "client_modified_at": "2026-07-14T10:00:00Z",
            "modified_at": "2026-07-14T12:00:00Z",
        }
        self.assertEqual(newest_side(local, server), "local")

    def test_old_manifest_falls_back_to_server_time(self) -> None:
        local = {"modified_at": "2026-07-14T10:00:00Z"}
        server = {"modified_at": "2026-07-14T11:00:00Z"}
        self.assertEqual(newest_side(local, server), "server")

    def test_invalid_client_time_falls_back_to_server_time(self) -> None:
        item = {
            "client_modified_at": "0001-01-01T00:00:00Z",
            "modified_at": "2026-07-14T11:00:00Z",
        }
        self.assertGreater(modified_timestamp(item), 0)

    def test_tied_or_unknown_times_remain_ambiguous(self) -> None:
        stamp = {"modified_at": "2026-07-14T10:00:00Z"}
        self.assertIsNone(newest_side(stamp, stamp))
        self.assertIsNone(newest_side({}, stamp))


if __name__ == "__main__":
    unittest.main()
