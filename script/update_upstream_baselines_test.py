#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import json
import tempfile
import unittest
from pathlib import Path

from script.update_upstream_baselines import update


class UpdateUpstreamBaselinesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for directory in (
            "dex-sdk/references/go",
            "dex-connector-contributor/references",
            "script",
            ".codex-plugin",
            ".claude-plugin",
            ".cursor-plugin",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        baselines = {
            "DEX_BASELINE": "sdk-go/v0.12.0",
            "DEX_SERVER_BASELINE": "server/v0.12.0",
            "DEX_CLI_BASELINE": "cli-v0.12.0",
            "TEMPLATE_BASELINE": "v0.2.0",
            "CONNECTOR_LIBRARY_BASELINE": "connectors/slack/v0.8.0",
            "VERSION": "1.2.3",
        }
        for name, value in baselines.items():
            (self.root / name).write_text(value + "\n")
        (self.root / "README.md").write_text(
            "basic-process release `v0.2.0`, Dex Server `v0.12.0`, "
            "Dex CLI `v0.12.0`.\n"
        )
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\nAll notable changes to Dex Skills are documented here.\n\n"
        )
        (self.root / "dex-sdk/references/go/go.md").write_text(
            "https://github.com/superdurable/dex/blob/sdk-go/v0.12.0/examples/go/main.go\n"
        )
        (self.root / "dex-connector-contributor/references/source.md").write_text(
            "https://github.com/superdurable/dex-connectors-library/blob/"
            "connectors/slack/v0.8.0/sdkgo/configuration_ui.go\n"
        )
        (self.root / "script/check-upstream-baselines.py").write_text(
            'if template_manifest.get("templateVersion") != "1.4.0":\n'
            '    fail("template baseline must be version 1.4.0")\n'
            'require_text(path, "github.com/superdurable/dex/sdk-go v0.12.0")\n'
        )
        for relative in (
            ".codex-plugin/plugin.json",
            ".claude-plugin/plugin.json",
            ".cursor-plugin/plugin.json",
        ):
            (self.root / relative).write_text(
                json.dumps({"name": "superdurable-dex", "version": "1.2.3"}, indent=2)
                + "\n"
            )
        for relative in (
            ".claude-plugin/marketplace.json",
            ".cursor-plugin/marketplace.json",
        ):
            (self.root / relative).write_text(
                json.dumps({"plugins": [{"version": "1.2.3"}]}, indent=2) + "\n"
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_updates_all_baselines_and_bumps_plugin_once(self) -> None:
        result = update(
            self.root,
            "sdk-go/v0.13.1",
            "server/v0.13.2",
            "cli-v0.13.8",
            "v0.3.0",
            "1.5.0",
            "v0.13.1",
            "connectors/google/gmail/v0.11.0",
            "2026-09-26",
        )
        self.assertEqual(result["changed"], "true")
        self.assertEqual((self.root / "VERSION").read_text(), "1.2.4\n")
        self.assertIn(
            "blob/sdk-go/v0.13.1/",
            (self.root / "dex-sdk/references/go/go.md").read_text(),
        )
        self.assertIn(
            "blob/connectors/google/gmail/v0.11.0/",
            (
                self.root / "dex-connector-contributor/references/source.md"
            ).read_text(),
        )
        checker = (self.root / "script/check-upstream-baselines.py").read_text()
        self.assertIn('templateVersion") != "1.5.0"', checker)
        self.assertIn("github.com/superdurable/dex/sdk-go v0.13.1", checker)
        self.assertIn("## 1.2.4 - 2026-09-26", (self.root / "CHANGELOG.md").read_text())

        second = update(
            self.root,
            "sdk-go/v0.13.1",
            "server/v0.13.2",
            "cli-v0.13.8",
            "v0.3.0",
            "1.5.0",
            "v0.13.1",
            "connectors/google/gmail/v0.11.0",
            "2026-09-26",
        )
        self.assertEqual(second["changed"], "false")
        self.assertEqual((self.root / "VERSION").read_text(), "1.2.4\n")

    def test_rejects_downgraded_release(self) -> None:
        with self.assertRaisesRegex(SystemExit, "older than the current baseline"):
            update(
                self.root,
                "sdk-go/v0.11.9",
                "server/v0.12.0",
                "cli-v0.12.0",
                "v0.2.0",
                "1.4.0",
                "v0.12.0",
                "connectors/slack/v0.8.0",
                "2026-09-26",
            )

    def test_rejects_invalid_connector_component_tag(self) -> None:
        with self.assertRaisesRegex(SystemExit, "not a stable component release"):
            update(
                self.root,
                "sdk-go/v0.12.0",
                "server/v0.12.0",
                "cli-v0.12.0",
                "v0.2.0",
                "1.4.0",
                "v0.12.0",
                "main",
                "2026-09-26",
            )


if __name__ == "__main__":
    unittest.main()
