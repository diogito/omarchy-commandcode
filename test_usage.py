#!/usr/bin/env python3
"""Offline checks for key discovery and the monthly meter. No network."""

from __future__ import annotations

import io
import json
import stat
import tempfile
import unittest
from pathlib import Path

import usage


class KeyDiscoveryTest(unittest.TestCase):
    def test_env_prefers_the_official_name(self) -> None:
        found = usage.load_key(
            {"COMMAND_CODE_API_KEY": "from-env", "CMD_API_KEY": "other"},
            paths=(),
        )
        self.assertEqual(found, "from-env")

    def test_cli_auth_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(json.dumps({"apiKey": "from-cli"}))
            self.assertEqual(usage.load_key({}, paths=(path,)), "from-cli")

    def test_pi_provider_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(json.dumps({"commandcode": {"type": "api", "key": "from-pi"}}))
            self.assertEqual(usage.load_key({}, paths=(path,)), "from-pi")

    def test_skips_unreadable_files(self) -> None:
        missing = Path("/tmp/omarchy-commandcode-missing-auth.json")
        self.assertEqual(usage.load_key({}, paths=(missing,)), "")


class MonthlyMeterTest(unittest.TestCase):
    def test_matches_spend_over_the_period_pool(self) -> None:
        limit = usage.monthly_limit(
            {"monthlyCredits": 80},
            {"totalMonthlyCredits": 20, "periodStart": "2026-01-01T00:00:00+00:00"},
            "2026-02-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        )
        self.assertIsNotNone(limit)
        assert limit is not None
        self.assertEqual(round(limit["percent"] * 100), 20)
        self.assertEqual(limit["resetStyle"], "date")

    def test_hides_monthly_when_the_periods_disagree(self) -> None:
        limit = usage.monthly_limit(
            {"monthlyCredits": 10},
            {"totalMonthlyCredits": 1, "periodStart": "2025-06-01T00:00:00+00:00"},
            "2026-02-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        )
        self.assertIsNone(limit)


class WindowMeterTest(unittest.TestCase):
    def test_percent_and_exceeded(self) -> None:
        limit = usage.window_limit({"used": 1, "cap": 100, "resetAt": 1_800_000_000_000}, "5-hour")
        self.assertIsNotNone(limit)
        assert limit is not None
        self.assertEqual(round(limit["percent"] * 100), 1)
        full = usage.window_limit({"used": 1, "cap": 14, "exceeded": True, "resetAt": 0}, "5-hour")
        self.assertIsNotNone(full)
        assert full is not None
        self.assertEqual(full["percent"], 1.0)


class StoreKeyTest(unittest.TestCase):
    def test_writes_a_private_auth_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "commandcode" / "auth.json"
            usage.store_key("user_example_key_0000000001", path)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            saved = json.loads(path.read_text())
            self.assertEqual(saved, {"apiKey": "user_example_key_0000000001"})
            self.assertFalse(path.with_name("auth.json.tmp").exists())

    def test_updates_an_existing_credential_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(json.dumps({"label": "keep", "key": "user_old_example_000000001"}))
            usage.store_key("user_new_example_000000001", path)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["label"], "keep")
            self.assertEqual(saved["key"], "user_new_example_000000001")
            self.assertNotIn("apiKey", saved)

    def test_rejects_a_key_with_spaces_and_leaves_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            pasted = "user_example key 0000000001"
            with self.assertRaises(usage.ApiError) as caught:
                usage.store_key(pasted, path)
            self.assertNotIn(pasted, str(caught.exception))
            self.assertFalse(path.exists())

    def test_env_override_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            report = usage.store_from_stdin(
                io.StringIO("user_example_key_0000000001\n"),
                env={"COMMAND_CODE_API_KEY": "user_from_the_environment_01"},
                path=path,
            )
            self.assertFalse(report["ok"])
            self.assertTrue(report["needsKey"])
            self.assertIn("COMMAND_CODE_API_KEY", report["error"])
            self.assertNotIn("user_from_the_environment_01", report["error"])
            self.assertNotIn("user_example_key_0000000001", report["error"])
            self.assertFalse(path.exists())

    def test_store_from_stdin_does_not_echo_the_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            report = usage.store_from_stdin(
                io.StringIO("short\n"),
                env={},
                path=path,
            )
            self.assertEqual(report["error"], usage.INVALID_KEY)
            self.assertNotIn("short", report["error"])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
