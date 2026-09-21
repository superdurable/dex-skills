#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("check-dex-ai-platform-sync.py")
SPEC = importlib.util.spec_from_file_location("sync_check", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PairedPlatformPullRequestTests(unittest.TestCase):
    def test_reads_exact_field(self) -> None:
        body = (
            "Summary\n\n"
            "Dex-AI-Platform-PR: "
            "https://github.com/superdurable/skill-dex-ai-platform/pull/42\n"
        )
        self.assertEqual(MODULE.paired_platform_pr(body), 42)

    def test_rejects_missing_field(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.paired_platform_pr("no pair")

    def test_rejects_wrong_repository(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.paired_platform_pr(
                "Dex-AI-Platform-PR: https://github.com/example/project/pull/42"
            )

    def test_rejects_duplicate_fields(self) -> None:
        field = (
            "Dex-AI-Platform-PR: "
            "https://github.com/superdurable/skill-dex-ai-platform/pull/42\n"
        )
        with self.assertRaises(SystemExit):
            MODULE.paired_platform_pr(field + field)


if __name__ == "__main__":
    unittest.main()
