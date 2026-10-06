#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "dex-app-builder" / "scripts"
INVENTORY = SCRIPTS / "n8n_inventory.py"
GOLDEN = SCRIPTS / "n8n_code_golden.mjs"
SECRET = "fixturekey0123456789abcdef"

RENDER_CODE = """let out = '';
for (row of $input.item.json.rows) {
  console.log(row)
  out += `<li>${row.label}: ${row.note}</li>`
}
return { html: out, setup: $('Settings').first().json.limit };"""


def synthetic_export():
    return {
        "name": "Synthetic digest",
        "nodes": [
            {"name": "Daily at 6am", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
             "parameters": {"rule": {"interval": [{"field": "hours", "triggerAtMinute": 15}]}}},
            {"name": "Settings", "type": "n8n-nodes-base.set", "typeVersion": 3.2,
             "parameters": {"fields": {"values": [
                 {"name": "apiKey", "stringValue": SECRET},
                 {"name": "limit", "type": "numberValue", "numberValue": "5"},
                 {"name": "unusedRecipients"},
             ]}}},
            {"name": "Read records", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4,
             "parameters": {"operation": "read", "documentId": {"__rl": True, "value": "sheet-1"}}},
            {"name": "Choose", "type": "n8n-nodes-base.if", "typeVersion": 2,
             "parameters": {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict"},
                                           "combinator": "or",
                                           "conditions": [
                                               {"operator": {"type": "string", "operation": "startsWith"},
                                                "leftValue": "={{ $json.title.toLowerCase() }}", "rightValue": "review"},
                                               {"operator": {"type": "string", "operation": "startsWith"},
                                                "leftValue": "={{ $json.title.toLowerCase() }}", "rightValue": "sync"},
                                           ]}}},
            {"name": "Normalize", "type": "n8n-nodes-base.set", "typeVersion": 3.2,
             "parameters": {"fields": {"values": [
                 {"name": "topic", "stringValue": "={{ $json.title.toLowerCase().replace('review', '').trim() }}"},
             ]}}},
            {"name": "Fetch", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.1,
             "parameters": {"url": "=https://api.example.test/search?q={{ $json.topic }}&from={{ $today.toFormat('yyyy-MM-dd') }}&limit={{ $('Settings').first().json.limit }}"}},
            {"name": "Render", "type": "n8n-nodes-base.code", "typeVersion": 2,
             "parameters": {"mode": "runOnceForEachItem", "jsCode": RENDER_CODE}},
            {"name": "Notify", "type": "n8n-nodes-base.gmail", "typeVersion": 2.1,
             "parameters": {"sendTo": "owner@example.test",
                            "subject": "=Digest for {{ $('Normalize').item.json.title }}",
                            "message": "={{ $json.html }}", "options": {}}},
            {"name": "Nothing", "type": "n8n-nodes-base.noOp", "typeVersion": 1, "parameters": {}},
            {"name": "Orphan", "type": "n8n-nodes-base.noOp", "typeVersion": 1, "parameters": {}},
            {"name": "Note", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
             "parameters": {"content": "Runs every morning."}},
        ],
        "connections": {
            "Daily at 6am": {"main": [[{"node": "Settings", "type": "main", "index": 0}]]},
            "Settings": {"main": [[{"node": "Read records", "type": "main", "index": 0}]]},
            "Read records": {"main": [[{"node": "Choose", "type": "main", "index": 0}]]},
            "Choose": {"main": [[{"node": "Normalize", "type": "main", "index": 0}],
                                [{"node": "Nothing", "type": "main", "index": 0}]]},
            "Normalize": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
            "Fetch": {"main": [[{"node": "Render", "type": "main", "index": 0}]]},
            "Render": {"main": [[{"node": "Notify", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.export = self.root / "export.json"
        self.export.write_text(json.dumps(synthetic_export()))
        self.out = self.root / "import"
        self.run_script("inventory", str(self.export), "--out", str(self.out))
        self.ledger = (self.out / "ledger.md").read_text()
        self.inventory = json.loads((self.out / "inventory.json").read_text())
        self.kinds = {finding["kind"] for finding in self.inventory["findings"]}

    def run_script(self, *arguments, check=True):
        result = subprocess.run(
            [sys.executable, "-B", str(INVENTORY), *arguments],
            capture_output=True, text=True,
        )
        if check and result.returncode != 0:
            self.fail(f"{arguments[0]} failed: {result.stderr}")
        return result

    def finding(self, kind):
        return [item for item in self.inventory["findings"] if item["kind"] == kind]

    def test_redacts_literal_secret_everywhere(self):
        self.assertIn("literal-secret", self.kinds)
        for output in (self.ledger, (self.out / "inventory.json").read_text()):
            self.assertNotIn(SECRET, output)
            self.assertIn("‹redacted›", output)

    def test_reports_schedule_label_mismatch(self):
        [mismatch] = self.finding("schedule-label-mismatch")
        self.assertIn("every hour at minute 15", mismatch["message"])
        self.assertEqual(self.inventory["schedules"][0]["cron"], "15 */1 * * *")

    def test_labels_branch_outputs(self):
        labels = {(edge["from"], edge["label"], edge["to"]) for edge in self.inventory["edges"]}
        self.assertIn(("Choose", "true", "Normalize"), labels)
        self.assertIn(("Choose", "false", "Nothing"), labels)

    def test_reports_semantic_risks(self):
        for kind in (
            "timezone-unset", "dead-config", "unreachable-node", "missing-field-throws",
            "unencoded-query", "literal-set-mismatch", "paired-item", "code-port",
            "js-coercion", "hardcoded-address", "version-default", "type-coercion",
        ):
            self.assertIn(kind, self.kinds)
        dead = " ".join(item["message"] for item in self.finding("dead-config"))
        self.assertIn("`unusedRecipients`", dead)
        self.assertNotIn("`limit`", dead)
        [mismatch] = self.finding("literal-set-mismatch")
        self.assertIn("sync", mismatch["message"])
        [orphan] = self.finding("unreachable-node")
        self.assertEqual(orphan["node"], "Orphan")

    def test_paired_item_reference_to_non_ancestor_is_reported(self):
        export = synthetic_export()
        export["connections"]["Render"] = {"main": [[]]}
        export["connections"]["Choose"]["main"][1].append({"node": "Notify", "type": "main", "index": 0})
        self.export.write_text(json.dumps(export))
        self.run_script("inventory", str(self.export), "--out", str(self.out))
        inventory = json.loads((self.out / "inventory.json").read_text())
        kinds = {finding["kind"] for finding in inventory["findings"]}
        self.assertIn("non-ancestor-reference", kinds)

    def test_verify_requires_every_row_resolved(self):
        ledger = self.out / "ledger.md"
        result = self.run_script("verify", str(ledger), check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("todo", result.stderr)

        resolved = re.sub(r"\| todo \|   \|", "| diverged |   |", self.ledger)
        ledger.write_text(resolved)
        result = self.run_script("verify", str(ledger), check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("needs notes", result.stderr)

        resolved = re.sub(r"\| todo \|   \|", "| dropped | not observable in this fixture |", self.ledger)
        ledger.write_text(resolved)
        result = self.run_script("verify", str(ledger))
        self.assertIn("ledger complete", result.stdout)

    def test_attached_sub_nodes_are_reachable_and_placeholders_are_not_secrets(self):
        export = synthetic_export()
        export["nodes"] += [
            {"name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 2, "parameters": {}},
            {"name": "Chat Model", "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1, "parameters": {}},
            {"name": "Keys", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "parameters": {"assignments": {"assignments": [
                {"name": "botToken", "type": "string", "value": "YOUR_BOT_TOKEN"}]}}},
        ]
        export["connections"]["Render"]["main"][0].append({"node": "Agent", "type": "main", "index": 0})
        export["connections"]["Agent"] = {"main": [[{"node": "Keys", "type": "main", "index": 0}]]}
        export["connections"]["Chat Model"] = {"ai_languageModel": [[{"node": "Agent", "type": "ai_languageModel", "index": 0}]]}
        self.export.write_text(json.dumps(export))
        self.run_script("inventory", str(self.export), "--out", str(self.out))
        inventory = json.loads((self.out / "inventory.json").read_text())
        unreachable = {item["node"] for item in inventory["findings"] if item["kind"] == "unreachable-node"}
        self.assertEqual(unreachable, {"Orphan"})
        placeholders = [item for item in inventory["findings"] if item["kind"] == "placeholder-secret"]
        self.assertEqual(len(placeholders), 1)
        secrets = [item for item in inventory["findings"] if item["kind"] == "literal-secret"]
        self.assertEqual({item["node"] for item in secrets}, {"Settings"})
        self.assertIn("YOUR_BOT_TOKEN", (self.out / "ledger.md").read_text())

    def test_rejects_non_workflow_input(self):
        self.export.write_text(json.dumps({"hello": "world"}))
        result = self.run_script("inventory", str(self.export), check=False)
        self.assertEqual(result.returncode, 2)


@unittest.skipUnless(shutil.which("node"), "node is required for the golden harness")
class GoldenHarnessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.export = self.root / "export.json"
        self.export.write_text(json.dumps(synthetic_export()))

    def golden(self, fixture, node="Render"):
        path = self.root / "fixture.json"
        path.write_text(json.dumps(fixture))
        return subprocess.run(
            ["node", str(GOLDEN), str(self.export), node, str(path)],
            capture_output=True, text=True,
        )

    def test_reproduces_javascript_coercion_per_item(self):
        result = self.golden({
            "items": [
                {"json": {"rows": [{"label": "a", "note": None}, {"label": "b"}]}},
                {"json": {"rows": []}},
            ],
            "nodes": {"Settings": [{"json": {"limit": 5}}]},
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output, [
            {"json": {"html": "<li>a: null</li><li>b: undefined</li>", "setup": 5}},
            {"json": {"html": "", "setup": 5}},
        ])
        self.assertIn("[console.log]", result.stderr)

    def test_a_thrown_error_is_golden_failure(self):
        result = self.golden({"items": [{"json": {}}], "nodes": {"Settings": [{"json": {}}]}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("node failed", result.stderr)

    def test_rejects_a_non_code_node(self):
        result = self.golden({"items": []}, node="Fetch")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
