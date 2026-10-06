#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inventory an n8n workflow export into a Dex import fidelity ledger.

Usage:
  n8n_inventory.py inventory EXPORT.json [--out DIRECTORY] [--catalog CATALOG.yaml]
  n8n_inventory.py verify LEDGER.md [--strict]

``inventory`` enumerates every node, connection, expression, credential
reference, literal secret, workflow setting, and known version-dependent
default, then writes ``ledger.md`` and ``inventory.json`` (or prints the ledger
when no directory is given). The ledger also carries a Mermaid graph of the
workflow, a draft connector capability matrix matched against a downloaded
Dex connector catalog, and a draft Dex plan. Literal secrets are redacted.

``verify`` fails while a ledger row is still ``todo``, while a ``diverged``,
``dropped``, ``blocked``, or ``pending`` row has no notes, or while a row that
``inventory.json`` (next to the ledger) generated is missing. ``pending`` marks
a proposal that still awaits the user's decision; ``--strict`` also fails on it.

The export is untrusted data: nothing in it is executed or followed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

STATUSES = ("mapped", "diverged", "dropped", "blocked", "pending")
DECISION_STATUSES = ("decided", "pending")
NOTE_REQUIRED = ("diverged", "dropped", "blocked", "pending")
WEBHOOK_OUTPUT_FIELDS = {"headers", "params", "query", "body", "webhookUrl", "executionMode"}
# Template placeholders such as [Company Name]; not Markdown link text and not all-caps log tags.
INLINE_PLACEHOLDER = re.compile(r"\[(?=[^\]]*[a-z])[A-Z][A-Za-z0-9 ]{1,40}\](?!\()")
SEVERITY_ORDER = ("critical", "high", "medium", "info")

SECRET_NAME = re.compile(
    r"(?i)(api.?key|access.?token|auth.?token|refresh.?token|token|secret|"
    r"passw(or)?d|private.?key|authorization|bearer)"
)
URL_SECRET = re.compile(
    r"[?&]([A-Za-z_\-]*(?:key|token|secret|password)[A-Za-z_\-]*)=([^&{}\s#'\"]+)",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(
    r"(?i)^(your[_\-\s]|<.*>$|\[.*\]$|x{4,}|placeholder|changeme|change[_\-]me|insert[_\-\s]|replace[_\-\s]|enter[_\-\s])"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EXPRESSION_SEGMENT = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
NODE_REFERENCE = re.compile(
    r"""\$\(\s*(['"])(.+?)\1\s*\)(?:\.(item|first|last|all|itemMatching|params|isExecuted)\b)?"""
)
LEGACY_NODE_REFERENCE = re.compile(r"""\$node\[\s*(['"])(.+?)\1\s*\]""")
JSON_FIELD = re.compile(
    r"""(?:\$json|\.json)(?:\.([A-Za-z_$][\w$]*)|\[\s*(['"])(.+?)\2\s*\])"""
)
TIME_DEPENDENT = re.compile(r"\$today|\$now|DateTime\.|new Date\(|Date\.now\(")
ENVIRONMENT = re.compile(r"\$env\b|\$vars\b|\$secrets\b")
STRING_REPLACE = re.compile(r"""\.replace\(\s*(['"])(.*?)\1""")
UNGUARDED_METHOD = re.compile(
    r"\$json\.[A-Za-z_$][\w$]*\.(?:(toLowerCase|toUpperCase|trim|split|replace|"
    r"startsWith|endsWith|includes|match|map|forEach|filter)\(|length\b)"
)
# A Code node member chain on an item field without optional chaining, such as items[0].json.list.length.
UNGUARDED_CODE_READ = re.compile(
    r"\.json\.[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\.(?:length\b|map\(|forEach\(|filter\(|toLowerCase\(|split\()"
    r"|\bfor\s*\(\s*(?:const|let|var)?\s*[A-Za-z_$][\w$]*\s+of\s+[^)]*\.json\.[A-Za-z_$][\w$.]*\s*\)"
)
LOCALE_DEPENDENT = re.compile(
    r"toLocale(?:String|DateString|TimeString)\(|\bIntl\.|toFormat\(\s*['\"](?:D{1,4}|t{1,4}|f{1,4}|F{1,4}|DD{0,3}\s*t{1,4})['\"]"
)
# Field names that hold a credential, as opposed to a pagination cursor or a counter.
CREDENTIAL_FIELD = re.compile(
    r"(?i)(api.?key|access.?token|auth.?token|refresh.?token|bot.?token|secret|passw(or)?d|private.?key|authorization|bearer|^token$|_token$)"
)
NON_CREDENTIAL_FIELD = re.compile(r"(?i)(page|next|cursor|continuation|sync|count|csrf|limit)")
DAY_WINDOW = re.compile(r"\$today|startOf\(\s*['\"]day['\"]\s*\)")
EMPTY_RESULT_CHECK = re.compile(r"\.length\s*(?:===?\s*0|<\s*1)|!\s*[\w$.]+\.length\b")
IDENTIFIER_KEY = re.compile(
    r"(?i)^(channel|chat|calendar|spreadsheet|document|folder|base|table|list|board|sheet|page|"
    r"database|project|team|workspace|repository|group|drive|playlist|form|space|pipeline|portal)(id|_id|ids)?$"
)
EFFECT_VERBS = ("send", "sendmessage", "create", "post", "append", "update", "upsert", "delete", "reply", "publish", "upload")
TEMPLATE_INTERPOLATION = re.compile(r"\$\{([^{}]*)\}")

TRIGGER_TYPES = {
    "scheduleTrigger", "cron", "interval", "manualTrigger", "start", "webhook",
    "formTrigger", "errorTrigger", "executeWorkflowTrigger", "n8nTrigger",
    "chatTrigger",
}
DEX_HINTS = {
    "scheduleTrigger": "Scheduler Flow on the Cron pattern: a Timer to the next occurrence in the source timezone starts one run Flow per occurrence, named <scheduler Flow ID>-run-<occurrence date> (Flow IDs reject /, $, and :).",
    "cron": "Scheduler Flow on the Cron pattern (legacy Cron node rules).",
    "interval": "Scheduler Flow on the Cron pattern with a fixed interval.",
    "manualTrigger": "Dex Web Start Flow with typed start input.",
    "start": "Dex Web Start Flow with typed start input.",
    "webhook": "webhook connector requestReceived Trigger; a synchronous response body needs a recorded capability check.",
    "respondToWebhook": "Synchronous webhook response: verify the webhook connector contract; likely a capability gap.",
    "formTrigger": "Dex Web Start Flow form or a participant Custom UI.",
    "errorTrigger": "Execute-failure recovery routes to an explicit recovery Step.",
    "executeWorkflowTrigger": "Typed start input of the Flow that replaces the sub-workflow.",
    "set": "Typed Go mapping inside the consuming application Step.",
    "if": "Go predicate in an application Step that chooses the next movement.",
    "filter": "Go predicate in an application Step; discarded items end without a movement.",
    "switch": "Go predicate in an application Step that chooses one movement per output.",
    "merge": "Join: await-all parallel Steps with a Channel count; replicate the merge mode exactly.",
    "noOp": "No behavior; drop and record.",
    "stickyNote": "Documentation only; drop from behavior and check its claims against the configuration.",
    "code": "Go application Step that ports the code, verified against golden output.",
    "function": "Go application Step that ports the code, verified against golden output.",
    "functionItem": "Go application Step that ports the code, verified against golden output.",
    "httpRequest": "Dedicated connector operation for that provider; the generic HTTP connector only for an organization-controlled internal service.",
    "wait": "Timer Condition, or a Channel/RPC resume for webhook or form resumes.",
    "splitInBatches": "Bounded dynamic parallel Steps or batched Steps.",
    "executeWorkflow": "Steps in the same Flow, or an independent top-level Flow under the Core boundary rules; no SubFlow by default.",
    "splitOut": "Pure Go transform in an application Step.",
    "aggregate": "Pure Go transform in an application Step.",
    "itemLists": "Pure Go transform in an application Step.",
    "removeDuplicates": "Pure Go transform; cross-execution deduplication needs durable state.",
    "sort": "Pure Go transform in an application Step.",
    "limit": "Pure Go transform in an application Step.",
    "summarize": "Pure Go transform in an application Step.",
    "dateTime": "Pure Go transform; keep the source timezone.",
    "html": "Pure Go transform in an application Step.",
    "markdown": "Pure Go transform in an application Step.",
    "xml": "Pure Go transform in an application Step.",
    "crypto": "Pure Go transform; keys belong to configuration, never Flow state.",
}
APP_HINT = "Released connector operation that matches this resource and operation in the catalog; a missing one is a connector contribution."
LANGCHAIN_HINT = "llm connector Query or a durable Dex agent; tools become Steps."
TRIGGER_HINT = "Released connector Trigger if the catalog has it; otherwise a connector contribution."

DEFAULT_RESOURCE = {"googleCalendar": "event", "gmail": "message", "slack": "message", "telegram": "message"}
# Candidate Dex catalog connector IDs for common n8n node types; the catalog decides what is released.
N8N_CONNECTOR_CANDIDATES = {
    "gmail": ["gmail"], "gmailTrigger": ["gmail"], "googleCalendar": ["google-calendar"],
    "googleSheets": ["google-sheets"], "googleDrive": ["google-drive"], "googleDocs": ["google-docs"],
    "slack": ["slack"], "slackTrigger": ["slack"], "hubspot": ["hubspot"], "notion": ["notion"],
    "airtable": ["airtable"], "emailSend": ["email"], "emailReadImap": ["email"], "webhook": ["webhook"],
    "openAi": ["openai", "llm"], "lmChatOpenAi": ["llm", "openai"], "lmChatGoogleGemini": ["llm", "gemini"],
    "lmChatAnthropic": ["llm"], "agent": ["llm"], "chainLlm": ["llm"], "jira": ["jira"], "github": ["github"],
    "stripe": ["stripe"], "stripeTrigger": ["stripe"], "typeform": ["typeform"], "typeformTrigger": ["typeform"],
    "linear": ["linear"], "asana": ["asana"], "trello": ["trello"], "salesforce": ["salesforce"],
    "zendesk": ["zendesk-support"], "microsoftOutlook": ["outlook-mail", "outlook-calendar"],
    "microsoftTeams": ["microsoft-teams"], "postgres": ["postgresql"], "mySql": ["mysql"],
    "twilio": ["twilio-messaging"], "mailchimp": ["mailchimp"], "pipedrive": ["pipedrive"], "awsS3": ["amazon-s3"],
}
# n8n operation verbs and the catalog operation-name prefixes they usually correspond to.
OPERATION_VERBS = {
    "getall": ["list", "search"], "getmany": ["list", "search"], "search": ["search", "list"], "get": ["get", "read"],
    "generate": ["generate", "create"], "sendmessage": ["send", "post"], "analyze": ["create", "generate"],
    "send": ["send", "post", "reply"], "create": ["create", "upsert", "post", "add"], "update": ["update", "upsert"],
    "upsert": ["upsert", "update"], "delete": ["delete", "cancel", "remove"], "read": ["get", "read", "list"],
    "append": ["append", "add", "create"], "post": ["post", "send", "create"],
}
MULTI_ITEM_OPERATIONS = ("getall", "getmany", "search", "list", "read", "readrows")
# n8n's default operation when a node's parameters omit it.
DEFAULT_OPERATION = {"gmail": "send", "emailSend": "send", "telegram": "sendMessage", "slack": "post", "agent": "generate", "chainLlm": "generate"}
# LangChain sub-nodes configure the consuming agent or chain; they are not separate provider calls.
LANGCHAIN_SUB_NODE_PREFIXES = {
    "lmChat": "model of the consuming agent or chain: the llm connection's provider and model",
    "lmOpenAi": "model of the consuming agent or chain: the llm connection's provider and model",
    "embeddings": "embedding model of the consuming chain",
    "outputParser": "structured output (JSON Schema) of the consuming agent's llm generateText request",
    "memory": "conversation memory: keep turns in Flow Attributes",
    "tool": "agent tool: an application Step, or a Connector Step for a provider tool",
    "textSplitter": "text splitting inside an application Step",
    "documentLoader": "document loading inside an application Step",
}
HTML_TAG = re.compile(r"<\s*(table|tr|td|div|a|p|li|ul|span|b|i|br|img)\b", re.IGNORECASE)
HEADER_PARAMETERS = ("subject", "title", "headers", "header")
MESSAGE_BODY_PARAMETERS = ("message", "html", "text", "body", "bodyContent", "content")
EMAIL_NODE_TYPES = ("gmail", "emailSend", "microsoftOutlook", "sendGrid", "mailgun", "mailjet", "awsSes")
LANGCHAIN_ROOT_PREFIXES = ("agent", "chain", "openAi", "anthropic", "googleGemini", "informationExtractor", "textClassifier", "sentimentAnalysis")
RECIPIENT_PARAMETERS = ("sendTo", "toEmail", "to", "toRecipients", "ccList", "bccList")
CORE_PACKAGES = ("n8n-nodes-base", "@n8n/n8n-nodes-langchain")
STRUCTURAL_PARAMETERS = {"resource", "operation", "authentication", "options"}
# Required fields of common send operations, keyed by (node, resource, operation) with n8n's defaults
# filled in; confirm each against the n8n node source at the exported version.
REQUIRED_PARAMETERS = {
    ("emailSend", "", "send"): ("fromEmail", "toEmail"),
    ("gmail", "message", "send"): ("sendTo", "message"),
    ("telegram", "message", "sendMessage"): ("chatId", "text"),
}


def short_type(node_type: str) -> str:
    return node_type.rsplit(".", 1)[-1]


def node_version(node: dict) -> float:
    try:
        return float(node.get("typeVersion", 1))
    except (TypeError, ValueError):
        return 1.0


def is_trigger(node: dict) -> bool:
    kind = short_type(node.get("type", ""))
    return kind in TRIGGER_TYPES or kind.endswith("Trigger")


def walk(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")
    else:
        yield path, value


def literal_text(text: str) -> str:
    """Return the non-expression part of a parameter value."""
    if text.startswith("="):
        return EXPRESSION_SEGMENT.sub("", text[1:])
    return text


def cell(text, limit: int = 220) -> str:
    rendered = " ".join(str(text).split())
    if len(rendered) > limit:
        rendered = rendered[: limit - 1] + "…"
    return rendered.replace("|", "\\|") or " "


class Inventory:
    def __init__(self, workflow: dict, source_name: str, catalog: list | None = None):
        self.workflow = workflow
        self.source_name = source_name
        self.catalog = catalog
        self.nodes = [node for node in workflow.get("nodes", []) if isinstance(node, dict)]
        self.by_name = {node.get("name", ""): node for node in self.nodes}
        self.secrets: set[str] = set()
        self.placeholders: set[tuple] = set()
        self.findings: list[dict] = []
        self.expressions: list[dict] = []
        self.edges: list[dict] = []
        self.credentials: dict[tuple, list[str]] = defaultdict(list)
        self.set_fields: list[dict] = []
        self.schedules: list[dict] = []
        self.claims: list[dict] = []
        self.node_rows: list[dict] = []
        self.grouped: dict[tuple, list[str]] = defaultdict(list)
        self.secret_fields: set[str] = set()
        self.ledger_ids: list[str] = []

    # ----- collection -------------------------------------------------
    def build(self) -> "Inventory":
        self.collect_edges()
        self.collect_secrets()
        for node in self.nodes:
            self.collect_node(node)
        self.emit_grouped()
        self.check_reachability()
        self.check_webhook_output_shape()
        self.check_branch_order()
        self.check_authentication_consistency()
        self.check_zero_item_stops()
        self.check_repeated_effects()
        self.check_secret_requests()
        self.check_model_output_bodies()
        self.check_merge_inputs()
        self.check_wait_loops()
        self.check_provenance()
        self.check_preflight()
        self.check_open_triggers()
        self.check_references()
        self.check_dead_fields()
        self.check_literal_sets()
        self.check_settings()
        self.findings.sort(key=lambda item: SEVERITY_ORDER.index(item["severity"]))
        return self

    def add_finding(self, severity: str, kind: str, node: str, message: str) -> None:
        self.findings.append(
            {"severity": severity, "kind": kind, "node": node, "message": message}
        )

    def group(self, kind: str, node: str, item: str) -> None:
        if item not in self.grouped[(kind, node)]:
            self.grouped[(kind, node)].append(item)

    def emit_grouped(self) -> None:
        for (kind, node), items in self.grouped.items():
            listed = ", ".join(f"`{item}`" for item in items)
            if kind == "timezone-dependent":
                self.add_finding("medium", kind, node,
                                 f"Reads the current time or date in the workflow timezone: {listed}. Compute it in the same IANA zone in Dex.")
            elif kind == "missing-field-empty":
                self.add_finding("medium", kind, node,
                                 f"Reads a member of an unguarded field in an expression: {listed}. For an item missing that field, n8n swallows the TypeError, so the value is empty and the node continues. "
                                 "Trace the empty value to the next predicate or provider call, record what happens there, and port that, not a failure.")
            elif kind == "missing-field-throws":
                self.add_finding("medium", kind, node,
                                 f"Code reads a member of an unguarded field: {listed}. An item missing that field throws, which fails the node and the whole execution; decide whether Dex reproduces the failure or treats it as a non-match.")
            elif kind == "hardcoded-address":
                self.add_finding("medium", kind, node,
                                 f"Literal address(es) {listed}; make them configuration or typed start input.")
            elif kind == "no-retry":
                self.add_finding("info", kind, node,
                                 f"n8n does not retry {listed} (retryOnFail is off); a Dex connector retries per its execution policy. Record that divergence.")
            elif kind == "missing-credential":
                self.add_finding("high", kind, node,
                                 f"No credential is attached to {listed}, so n8n cannot run them as exported and the account they act for is unknown. Ask which account each Dex connection authorizes.")
            elif kind == "hardcoded-identifier":
                self.add_finding("medium", kind, node,
                                 f"Literal identifier(s) {listed} name one account's resources; make them configuration or typed start input.")
            elif kind == "locale-dependent":
                self.add_finding("medium", kind, node,
                                 f"Formats with the runtime locale or a locale-dependent macro ({listed}); the n8n instance's locale and timezone decide the text. Pin both in Go and capture goldens under the same locale.")
            elif kind == "community-node":
                self.add_finding("high", kind, node,
                                 f"Community node(s) {listed}: behavior and defaults come from that package, not n8n core. Read the package source at the exported version, or mark the rows `pending` until the user confirms the behavior.")
            elif kind == "operation-check":
                self.add_finding("info", kind, node,
                                 f"Check each resource and operation against the node's option list at its typeVersion: {listed}. n8n never validates these values, "
                                 "and an unknown one does something node-specific, from an error to an empty item with no provider call.")
            elif kind == "literal-placeholder":
                self.add_finding("medium", kind, node,
                                 f"Literal template placeholder(s) {listed} would be sent as written; ask for the real value or a field to fill it.")

    def collect_edges(self) -> None:
        connections = self.workflow.get("connections", {}) or {}
        for source, outputs in connections.items():
            if not isinstance(outputs, dict):
                continue
            for connection_type, branches in outputs.items():
                for index, targets in enumerate(branches or []):
                    for target in targets or []:
                        self.edges.append({
                            "from": source,
                            "type": connection_type,
                            "output": index,
                            "label": self.output_label(source, connection_type, index),
                            "to": target.get("node", ""),
                            "input": target.get("index", 0),
                        })

    def output_label(self, source: str, connection_type: str, index: int) -> str:
        if connection_type != "main":
            return connection_type
        node = self.by_name.get(source, {})
        kind = short_type(node.get("type", ""))
        if kind == "if":
            return "true" if index == 0 else "false"
        if kind == "filter":
            return "kept" if index == 0 else "discarded"
        if kind == "splitInBatches" and node_version(node) >= 3:
            return "done" if index == 0 else "loop"
        if kind == "switch":
            rules = node.get("parameters", {}).get("rules", {}).get("values", [])
            if index < len(rules) and rules[index].get("outputKey"):
                return f"output {index} ({rules[index]['outputKey']})"
            return f"output {index}"
        return "main" if index == 0 else f"output {index}"

    def collect_secrets(self) -> None:
        for node in self.nodes:
            name = node.get("name", "")
            parameters = node.get("parameters", {}) or {}
            for field in self.node_set_fields(node):
                value = field.get("value")
                if isinstance(value, str) and SECRET_NAME.search(field["name"] or ""):
                    self.secret_fields.add(field["name"])
                    self.record_secret(name, f"Set field `{field['name']}`", value)
            for path, value in walk(parameters):
                if not isinstance(value, str):
                    continue
                key = re.split(r"[.\[]", path)[-1]
                if SECRET_NAME.search(key) and not value.startswith("="):
                    self.record_secret(name, f"parameter `{path}`", value)
                for match in URL_SECRET.finditer(literal_text(value)):
                    self.record_secret(name, f"URL query `{match.group(1)}` in `{path}`", match.group(2))
            for entry in self.name_value_pairs(parameters):
                if SECRET_NAME.search(entry[0]) and not entry[1].startswith("="):
                    self.record_secret(name, f"header or query `{entry[0]}`", entry[1])

    def record_secret(self, node: str, where: str, value: str) -> None:
        value = value.strip()
        if PLACEHOLDER.search(value):
            if (node, value) in self.placeholders:
                return
            self.placeholders.add((node, value))
            self.add_finding(
                "info", "placeholder-secret", node,
                f"Placeholder credential in {where}; the real value belongs in the connector connection, never in source or Flow state.",
            )
            return
        if len(value) < 8 or value in self.secrets:
            return
        self.secrets.add(value)
        self.add_finding(
            "critical", "literal-secret", node,
            f"Literal secret in {where} ({len(value)} characters, redacted). Move it to the connector "
            "connection, keep it out of source, Flow state, fixtures, and logs, and rotate it if the "
            "export was shared.",
        )

    @staticmethod
    def name_value_pairs(parameters: dict):
        stack = [parameters]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                name, value = current.get("name"), current.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    yield name, value
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

    @staticmethod
    def node_set_fields(node: dict) -> list[dict]:
        if short_type(node.get("type", "")) != "set":
            return []
        parameters = node.get("parameters", {}) or {}
        fields = []
        for entry in parameters.get("fields", {}).get("values", []) or []:
            kind = entry.get("type", "stringValue")
            fields.append({"name": entry.get("name", ""), "type": kind, "value": entry.get(kind, "")})
        for entry in parameters.get("assignments", {}).get("assignments", []) or []:
            fields.append({"name": entry.get("name", ""), "type": entry.get("type", "string"), "value": entry.get("value", "")})
        values = parameters.get("values", {})
        if isinstance(values, dict):
            for kind, entries in values.items():
                for entry in entries or []:
                    fields.append({"name": entry.get("name", ""), "type": kind, "value": entry.get("value", "")})
        return fields

    def collect_node(self, node: dict) -> None:
        name = node.get("name", "")
        kind = short_type(node.get("type", ""))
        version = node_version(node)
        parameters = node.get("parameters", {}) or {}

        for credential_type, reference in (node.get("credentials") or {}).items():
            label = reference.get("name", "") if isinstance(reference, dict) else str(reference)
            self.credentials[(credential_type, label)].append(name)
            if isinstance(reference, dict) and (not reference.get("id") or any(str(key).startswith("__") for key in reference)):
                self.add_finding("medium", "managed-credential", name,
                                 f"The `{credential_type}` reference has no credential ID ({', '.join(sorted(str(key) for key in reference if str(key).startswith('__'))) or 'not exported'}): n8n manages or omits it, so nothing about the account carries over. The Dex connection uses an account and key the user supplies.")
        self.collect_identifiers(name, kind, parameters)

        for field in self.node_set_fields(node):
            self.set_fields.append({"node": name, **field})
            if field["type"] == "numberValue" and isinstance(field["value"], str):
                self.add_finding("info", "type-coercion", name,
                                 f"Field `{field['name']}` is a number field holding the string {field['value']!r}; n8n coerces it to a number.")

        for path, value in walk(parameters):
            if isinstance(value, str) and kind not in ("stickyNote", "code", "function", "functionItem") and "cachedResult" not in path:
                for placeholder in sorted(set(INLINE_PLACEHOLDER.findall(literal_text(value)))):
                    self.group("literal-placeholder", name, f"{placeholder}` in `{path}")
            if isinstance(value, str) and value.startswith("="):
                self.collect_expression(node, path, value)
            elif isinstance(value, str) and path.split(".")[-1] in RECIPIENT_PARAMETERS and "," in value:
                self.add_finding("info", "recipient-list", name,
                                 f"`{path}` holds a comma-separated address list; Dex email connectors take one address per entry and reject duplicates.")
                for address in sorted(set(EMAIL.findall(value))):
                    self.group("hardcoded-address", name, f"{address}` in `{path}")
            elif isinstance(value, str) and kind != "stickyNote" and "cachedResult" not in path:
                for address in sorted(set(EMAIL.findall(value))):
                    self.group("hardcoded-address", name, f"{address}` in `{path}")

        if kind in ("code", "function", "functionItem"):
            self.collect_code(node)
        if kind == "scheduleTrigger" or kind == "cron":
            self.collect_schedule(node)
        if kind == "stickyNote":
            self.claims.append({"source": f"Sticky note `{name}`", "text": parameters.get("content", "").strip()})
        self.collect_settings_flags(node)
        self.collect_version_defaults(node)
        self.check_runnable(node)
        if kind == "httpRequest" or (self.is_app_node(node) and not is_trigger(node)):
            if not node.get("retryOnFail"):
                self.group("no-retry", f"{kind} nodes", name)

        self.node_rows.append({
            "node": name,
            "type": f"{kind}@{version:g}",
            "behavior": self.describe(node),
            "hint": self.hint(node),
        })

    def collect_identifiers(self, name: str, kind: str, parameters, path: str = "") -> None:
        """Group literal resource identifiers, such as a channel or spreadsheet ID, that belong in configuration."""
        if kind in ("stickyNote", "code", "function", "functionItem", "set"):
            return
        if isinstance(parameters, dict):
            for key, value in parameters.items():
                child = f"{path}.{key}" if path else str(key)
                if key == "cachedResultName" or key == "cachedResultUrl":
                    continue
                if isinstance(value, dict) and value.get("__rl"):
                    literal = value.get("value")
                    if IDENTIFIER_KEY.match(str(key)) and isinstance(literal, str) and literal and not literal.startswith("=") and not EMAIL.fullmatch(literal):
                        self.group("hardcoded-identifier", name, f"{literal}` in `{child}")
                elif isinstance(value, (dict, list)):
                    self.collect_identifiers(name, kind, value, child)
                elif IDENTIFIER_KEY.match(str(key)) and isinstance(value, str) and value and not value.startswith("=") and not EMAIL.fullmatch(value):
                    self.group("hardcoded-identifier", name, f"{value}` in `{child}")
        elif isinstance(parameters, list):
            for index, value in enumerate(parameters):
                self.collect_identifiers(name, kind, value, f"{path}[{index}]")

    def is_app_node(self, node: dict) -> bool:
        kind = short_type(node.get("type", ""))
        package = node.get("type", "").rsplit(".", 1)[0]
        if package == "@n8n/n8n-nodes-langchain":
            # Vendor nodes, such as openAi, call the provider directly; agents, chains, and sub-nodes do not.
            return bool((node.get("parameters", {}) or {}).get("resource")) and not langchain_sub_node_role(node) \
                and not kind.startswith(("agent", "chain")) and not is_trigger(node)
        return kind not in DEX_HINTS and kind not in TRIGGER_TYPES

    def check_runnable(self, node: dict) -> None:
        """Report integration nodes that the export cannot run as written."""
        name = node.get("name", "")
        kind = short_type(node.get("type", ""))
        package = node.get("type", "").rsplit(".", 1)[0]
        parameters = node.get("parameters", {}) or {}
        if package not in CORE_PACKAGES:
            self.group("community-node", package, name)
        if kind.startswith("lmChat") or kind.startswith("lmOpenAi") or (package == "@n8n/n8n-nodes-langchain" and "modelId" in parameters):
            model = parameters.get("model", parameters.get("modelName", parameters.get("modelId")))
            selected = model.get("value") if isinstance(model, dict) else model
            if "model" in parameters or "modelName" in parameters or "modelId" in parameters:
                if not selected:
                    self.add_finding("high", "hollow-node", name,
                                     "The model selector is empty, so n8n cannot run this model as exported. Ask which provider and model the Dex llm connection uses.")
        if not self.is_app_node(node) or node.get("disabled"):
            return
        resource = parameters.get("resource", DEFAULT_RESOURCE.get(kind, "(default)"))
        self.group("operation-check", "(workflow)", f"{name}: {kind}@{node_version(node):g} {resource}/{parameters.get('operation', DEFAULT_OPERATION.get(kind, '(default)'))}")
        if not node.get("credentials"):
            self.group("missing-credential", f"{kind} nodes", name)
        payload = set(parameters) - STRUCTURAL_PARAMETERS
        key = (kind, str(parameters.get("resource", DEFAULT_RESOURCE.get(kind, ""))),
               str(parameters.get("operation", DEFAULT_OPERATION.get(kind, ""))))
        missing = [field for field in REQUIRED_PARAMETERS.get(key, ()) if not parameters.get(field)]
        if not payload or missing:
            detail = f"missing required {', '.join(missing)}" if missing else "only its resource and operation are set"
            self.add_finding("high", "hollow-node", name,
                             f"The node is a placeholder ({detail}; confirm in the node source at typeVersion {node_version(node):g}), so n8n cannot run it as exported. "
                             "Its real behavior must come from the user, not from notes or the node name.")

    def hint(self, node: dict) -> str:
        kind = short_type(node.get("type", ""))
        if "langchain" in node.get("type", ""):
            return LANGCHAIN_HINT
        if kind in DEX_HINTS:
            return DEX_HINTS[kind]
        if is_trigger(node):
            return TRIGGER_HINT
        return APP_HINT

    def describe(self, node: dict) -> str:
        kind = short_type(node.get("type", ""))
        parameters = node.get("parameters", {}) or {}
        parts = []
        if node.get("disabled"):
            parts.append("DISABLED (passes items through unchanged)")
        if kind == "set":
            fields = ", ".join(
                f"{field['name']}={self.short_value(field['value'])}" for field in self.node_set_fields(node)
            )
            parts.append(f"sets {fields or 'no fields'}")
        elif kind in ("if", "filter"):
            parts.append(self.describe_conditions(parameters))
        elif kind == "httpRequest":
            parts.append(f"{parameters.get('method', 'GET')} {self.short_value(parameters.get('url', ''), 120)}")
        elif kind in ("code", "function", "functionItem"):
            code = parameters.get("jsCode") or parameters.get("functionCode") or parameters.get("pythonCode") or ""
            mode = parameters.get("mode", "runOnceForAllItems" if kind != "functionItem" else "runOnceForEachItem")
            parts.append(f"{parameters.get('language', 'javaScript')}, {mode}, {len(code.splitlines())} lines")
        elif kind in ("scheduleTrigger", "cron"):
            parts.append("; ".join(schedule["description"] for schedule in self.schedules if schedule["node"] == node.get("name")))
        elif kind == "noOp":
            parts.append("no effect")
        elif kind == "stickyNote":
            parts.append("note: " + self.short_value(parameters.get("content", "").strip(), 120))
        else:
            resource = parameters.get("resource", DEFAULT_RESOURCE.get(kind, ""))
            operation = parameters.get("operation", DEFAULT_OPERATION.get(kind, ""))
            if self.is_app_node(node) and not is_trigger(node):
                resource = resource or "(node default resource)"
                operation = operation or "(node default operation)"
            if resource or operation:
                parts.append("/".join(part for part in (resource, operation) if part))
            for key, value in parameters.items():
                if key in ("resource", "operation", "options"):
                    continue
                if isinstance(value, dict) and value.get("__rl"):
                    parts.append(f"{key}={value.get('value')} (fixed resource)")
                elif isinstance(value, (str, int, float, bool)) and value != "":
                    parts.append(f"{key}={self.short_value(value, 80)}")
                elif isinstance(value, (dict, list)) and value:
                    parts.append(f"{key}={self.short_value(value, 120)}")
            options = parameters.get("options")
            if isinstance(options, dict):
                parts.append("options: " + (", ".join(sorted(options)) or "none (all defaults)"))
        return "; ".join(part for part in parts if part)

    def short_value(self, value, limit: int = 60) -> str:
        # Redact before truncating, so a cut inside a secret never leaves its prefix behind.
        text = self.redact(json.dumps(value) if not isinstance(value, str) else value)
        return text if len(text) <= limit else text[: limit - 1] + "…"

    @staticmethod
    def describe_conditions(parameters: dict) -> str:
        block = parameters.get("conditions", {}) or {}
        conditions = block.get("conditions")
        if isinstance(conditions, list):
            rendered = []
            for condition in conditions:
                operator = condition.get("operator", {})
                rendered.append(
                    f"{condition.get('leftValue', '')} {operator.get('operation', '?')} {json.dumps(condition.get('rightValue', ''))}"
                )
            options = block.get("options", {})
            return (
                f" {block.get('combinator', 'and').upper()} ".join(rendered)
                + f" (caseSensitive={json.dumps(options.get('caseSensitive', True))}, typeValidation={options.get('typeValidation', 'strict')})"
            )
        return "legacy conditions: " + json.dumps(block)[:160]

    def collect_expression(self, node: dict, path: str, value: str) -> None:
        name = node.get("name", "")
        body = value[1:]
        segments = EXPRESSION_SEGMENT.findall(body) or [body]
        semantics = []
        references = sorted({match.group(2) for match in NODE_REFERENCE.finditer(body)}
                            | {match.group(2) for match in LEGACY_NODE_REFERENCE.finditer(body)})
        if references:
            semantics.append("reads node(s) " + ", ".join(references))
        if re.search(r"\$\([^)]*\)\.item\b", body):
            semantics.append("paired-item lineage: carry the upstream field explicitly in Dex Step input")
            self.add_finding("info", "paired-item", name,
                             f"`{path}` resolves an upstream item through paired-item lineage; Dex has no implicit lineage, so carry that field in the Step input or an AttributeMap entry.")
        fields = sorted({match.group(1) or match.group(3) for match in JSON_FIELD.finditer(body)})
        if fields:
            semantics.append("fields " + ", ".join(fields))
        if TIME_DEPENDENT.search(body):
            semantics.append("timezone-dependent (workflow timezone)")
            self.group("timezone-dependent", name, path)
        if LOCALE_DEPENDENT.search(body):
            semantics.append("locale-dependent formatting")
            self.group("locale-dependent", name, path)
        if ENVIRONMENT.search(body):
            semantics.append("reads instance environment or variables")
            self.add_finding("high", "environment", name,
                             f"`{path}` reads $env/$vars/$secrets, which the export does not contain; map each to configuration.")
        for match in STRING_REPLACE.finditer(body):
            semantics.append(f"String.replace({match.group(2)!r}) replaces only the first occurrence")
        if UNGUARDED_METHOD.search(body):
            semantics.append("a missing field makes this segment empty: n8n swallows the TypeError and the node continues")
            self.group("missing-field-empty", name, path)
        if path.split(".")[-1] in HEADER_PARAMETERS and (JSON_FIELD.search(body) or NODE_REFERENCE.search(body)):
            semantics.append("an upstream value can carry a line break into a header")
            self.add_finding("info", "header-line-break", name,
                             f"`{path}` interpolates an upstream value into a header; email connectors reject CR or LF in a subject, so decide whether line breaks become spaces.")
        if path.split(".")[-1].lower() == "url" and "?" in body:
            query = body.split("?", 1)[1]
            if "{{" in query and "encodeURIComponent" not in query:
                semantics.append("interpolates into the query string without encoding")
                self.add_finding("medium", "unencoded-query", name,
                                 f"`{path}` concatenates values into the query string; n8n's URL parsing turns spaces into %20, while &, #, and + in a value change the query. Proper encoding in Dex is a recorded divergence.")
        self.expressions.append({
            "node": name,
            "parameter": path,
            "expression": " ⏎ ".join(segment.strip() for segment in segments),
            "semantics": semantics,
            "references": references,
        })

    def collect_code(self, node: dict) -> None:
        name = node.get("name", "")
        parameters = node.get("parameters", {}) or {}
        language = parameters.get("language", "javaScript")
        code = parameters.get("jsCode") or parameters.get("functionCode") or parameters.get("pythonCode") or ""
        if language.lower().startswith("python"):
            self.add_finding("high", "python-code", name,
                             "Python Code node: the golden harness runs only JavaScript; capture golden output from an n8n execution instead.")
        if "console.log" in code:
            self.add_finding("info", "debug-logging", name, "console.log writes only n8n execution logs; drop it and record the drop.")
        interpolations = [" ".join(match.group(1).split()) for match in TEMPLATE_INTERPOLATION.finditer(code)]
        interpolations = sorted({item for item in interpolations if item})
        if interpolations:
            self.add_finding("medium", "js-coercion", name,
                             f"{len(interpolations)} template-literal interpolation(s), such as "
                             + ", ".join(f"`{item[:60]}`" for item in interpolations[:4])
                             + "; JavaScript renders null as 'null', undefined as 'undefined', and objects as '[object Object]', and NaN serializes as null in output items. The Go port must match the golden output.")
        if HTML_TAG.search(code) and interpolations and "escape" not in code.lower():
            self.add_finding("medium", "raw-html-interpolation", name,
                             "The code inserts upstream values into HTML without escaping, so provider markup renders and a stray < or & changes the page. Port it byte for byte first, then decide escaping explicitly.")
        mode = parameters.get("mode", "runOnceForAllItems")
        if node_version(node) >= 2 and short_type(node.get("type", "")) == "code" and mode == "runOnceForAllItems":
            first_item_reads = sorted(set(re.findall(r"\$input\.item\b|\$json\b", code)))
            if first_item_reads:
                self.add_finding("high", "first-item-only", name,
                                 f"Run Once for All Items mode, yet the code reads {', '.join(first_item_reads)}, which n8n resolves to the first input item only; "
                                 "the other items are ignored unless the code iterates $input.all(). Port that behavior, or record the fix as a decision.")
        if TIME_DEPENDENT.search(code):
            self.group("timezone-dependent", name, "code")
        for match in LOCALE_DEPENDENT.finditer(code):
            self.group("locale-dependent", name, match.group(0))
        for match in UNGUARDED_CODE_READ.finditer(code):
            self.group("missing-field-throws", name, " ".join(match.group(0).split())[:60])
        if re.search(r"\bfor\s*\(\s*[A-Za-z_$][\w$]*\s+of\b", code):
            self.add_finding("info", "js-implicit-global", name, "A for-of loop assigns an undeclared variable (sloppy-mode implicit global); keep the harness in sloppy mode.")
        for match in NODE_REFERENCE.finditer(code):
            self.expressions.append({
                "node": name, "parameter": "code", "expression": match.group(0),
                "semantics": ["reads node " + match.group(2)], "references": [match.group(2)],
            })
        self.add_finding("high", "code-port", name,
                         f"Port this Code node to a Go application Step and prove parity with golden output from `node n8n_code_golden.mjs EXPORT {json.dumps(name)} FIXTURE.json`, including empty and null-valued inputs.")

    def collect_schedule(self, node: dict) -> None:
        name = node.get("name", "")
        kind = short_type(node.get("type", ""))
        parameters = node.get("parameters", {}) or {}
        rules = []
        if kind == "scheduleTrigger":
            for rule in parameters.get("rule", {}).get("interval", []) or [{}]:
                rules.append(describe_schedule_rule(rule))
        else:
            for item in parameters.get("triggerTimes", {}).get("item", []) or []:
                rules.append({"description": f"legacy Cron node rule {json.dumps(item)}", "field": item.get("mode", ""), "hour": item.get("hour"), "cron": ""})
        for rule in rules:
            self.schedules.append({"node": name, **rule})
            mismatch = schedule_label_mismatch(name, rule)
            if mismatch:
                self.add_finding("high", "schedule-label-mismatch", name,
                                 f"The name says {mismatch!r} but the rule fires {rule['description']}. The configured rule is the source behavior; ask which one the user intends.")
        self.claims.append({"source": f"Trigger name `{name}`", "text": name})

    def collect_settings_flags(self, node: dict) -> None:
        name = node.get("name", "")
        if node.get("disabled"):
            self.add_finding("medium", "disabled-node", name, "Disabled node: n8n skips it and passes items through unchanged.")
        on_error = node.get("onError") or ("continueRegularOutput" if node.get("continueOnFail") else "")
        if on_error and on_error != "stopWorkflow":
            self.add_finding("high", "on-error", name, f"onError={on_error}: failures become items or an error output instead of stopping the execution.")
        if node.get("alwaysOutputData"):
            self.add_finding("medium", "always-output-data", name, "alwaysOutputData: emits one empty item when there is no output, so downstream nodes still run.")
        if node.get("executeOnce"):
            self.add_finding("medium", "execute-once", name, "executeOnce: runs only for the first input item.")
        if node.get("retryOnFail"):
            self.add_finding("info", "retry", name,
                             f"retryOnFail: maxTries={node.get('maxTries', 3)}, waitBetweenTries={node.get('waitBetweenTries', 1000)}ms; map to the Step retry policy.")

    def collect_version_defaults(self, node: dict) -> None:
        name = node.get("name", "")
        kind = short_type(node.get("type", ""))
        version = node_version(node)
        parameters = node.get("parameters", {}) or {}
        options = parameters.get("options", {}) or {}
        note = None
        if kind == "set":
            if version < 3.3:
                note = "Set before v3.3 keeps all input fields next to the set fields by default; downstream reads may rely on those pass-through fields."
            elif not parameters.get("includeOtherFields"):
                note = "Set v3.3+ drops input fields unless includeOtherFields is on."
            if version >= 3:
                conversion = {3.0: "a string field that resolves to null or undefined becomes the text 'null' or 'undefined'",
                              3.1: "a string field that resolves to null or undefined fails the node unless ignoreConversionErrors is on"}.get(
                    version, "a field that resolves to null or undefined becomes null")
                extra = f"At v{version:g}, {conversion}; binary data is dropped{' unless input fields are kept' if version >= 3.4 else ' unless includeBinary is set'}."
                note = f"{note} {extra}" if note else extra
        elif kind == "gmail" and version >= 2.1 and parameters.get("operation", "send") == "send":
            if options.get("appendAttribution", True):
                note = ("Gmail v2.1+ send appends the footer 'This email was sent automatically with n8n' unless options.appendAttribution is false (reply never appends it). "
                        f"emailType is {options.get('emailType', parameters.get('emailType', 'html (default)'))}; html mail has no text/plain part, and the message is trimmed. Record the footer as a divergence.")
        elif kind == "emailSend" and version >= 2.1 and options.get("appendAttribution", True):
            note = "Send Email v2.1 appends 'This email was sent automatically with n8n' unless options.appendAttribution is false. Record the footer as a divergence."
        elif kind == "telegram" and parameters.get("resource", "message") == "message" and parameters.get("operation", "sendMessage") == "sendMessage":
            fields = parameters.get("additionalFields", {}) or {}
            parse_mode = fields.get("parse_mode", "Markdown")
            note = f"Telegram sendMessage sends parse_mode {parse_mode} ({'the default when unset' if 'parse_mode' not in fields else 'set'}), so the text is parsed as markup."
            if version >= 1.1 and fields.get("appendAttribution", True) and parse_mode in ("Markdown", "HTML"):
                note += " v1.1+ appends 'This message was sent automatically with n8n' unless appendAttribution is false."
            if version >= 1.2:
                note += " v1.2+ disables link previews by default."
        elif (kind == "slack" and version >= 2.1 and parameters.get("operation", "post") in ("post", "update")
              and (parameters.get("otherOptions", {}) or {}).get("includeLinkToWorkflow", True) is not False):
            note = "Slack v2.1+ appends an 'Automated with this n8n workflow' link unless otherOptions.includeLinkToWorkflow is false. Record it as a divergence."
        elif (kind == "microsoftTeams" and version >= 1.1 and parameters.get("operation", "create") == "create"
              and options.get("includeLinkToWorkflow", True) is not False):
            note = "Microsoft Teams v1.1+ appends a 'Powered by this n8n workflow' link and sends HTML unless includeLinkToWorkflow is false. Record it as a divergence."
        elif kind == "googleCalendar" and parameters.get("operation") == "getAll":
            if not parameters.get("returnAll"):
                note = f"Google Calendar getAll returns one page of {parameters.get('limit', 50)} events (default 50) without paging; order is unspecified unless options.orderBy is set."
        elif kind == "httpRequest" and version >= 3:
            if not options.get("response", {}).get("response", {}).get("neverError"):
                note = ("HTTP Request v3+: every item's request starts at once (options.batching only spaces the starts), and a non-2xx response fails the node "
                        "and the execution after all requests settle; the timeout is 300000 ms unless options.timeout is set.")
        elif kind in ("if", "filter", "switch") and version >= 2:
            note = (f"{kind} v{version:g}: typeValidation {((parameters.get('conditions', {}) or {}).get('options', {}) or {}).get('typeValidation', 'strict')}, but null and undefined pass it; "
                    "string operators compare leftValue ?? '' and exists/notExists test null, undefined, and NaN. A TypeError inside a condition expression leaves it empty instead of failing. "
                    "Only a type mismatch of a present value or an n8n ExpressionError fails the node.")
        elif kind == "code":
            note = f"Code v2 mode is {parameters.get('mode', 'runOnceForAllItems')}; runOnceForEachItem returns one item per input item."
        elif kind == "scheduleTrigger":
            note = ("Schedule Trigger fires in the workflow timezone (settings.timezone, else the instance GENERIC_TIMEZONE, which defaults to America/New_York). "
                    "An omitted hour or minute is 0, and the second is jittered except on seconds and cron rules. Executions may overlap. "
                    "The default scheduler never runs a missed occurrence; deduplication per scheduled time exists from n8n 2.19, and misfire options from typeVersion 1.4 on the opt-in durable scheduler. Record the instance's release.")
        elif kind == "wait":
            resume = parameters.get("resume", "timeInterval")
            if resume == "timeInterval":
                amount = parameters.get("amount", 1 if version < 1.1 else 5)
                unit = parameters.get("unit", "hours" if version < 1.1 else "seconds")
                seconds = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}.get(str(unit), 0) * (amount if isinstance(amount, (int, float)) else 0)
                note = (f"Wait resumes {amount} {unit} after the Wait node runs ({'defaults: amount 1, unit hours' if version < 1.1 else 'defaults: amount 5, unit seconds'})"
                        + ("; a day is exactly 24 hours, not a calendar day" if unit == "days" else "") + ". "
                        + ("The execution sleeps in place (under 65 seconds), and sibling branches that have not run wait too."
                           if 0 < seconds < 65 else
                           "A wait of 65 seconds or more pauses the whole execution, including sibling branches that have not run, "
                           "and resumes it on the workflow as it was when the execution started."))
            else:
                note = (f"Wait resume={resume}: the execution pauses until {'a call to its resume URL' if resume == 'webhook' else 'the form is submitted' if resume == 'form' else 'the specified time'}"
                        f"{'; limitWaitTime is off by default, so it can wait forever' if resume in ('webhook', 'form') else ''}.")
        elif kind == "webhook":
            method = parameters.get("httpMethod", "GET (default)")
            note = (f"Webhook httpMethod {method}, authentication {parameters.get('authentication', 'none (default)')}, responseMode {parameters.get('responseMode', 'onReceived (default)')}. "
                    "Each request starts its own execution with one item {headers, params, query, body, webhookUrl, executionMode}: a JSON body is parsed into body, "
                    "urlencoded and multipart fields land in body as strings, multipart files in binary. onReceived answers 200 {\"message\":\"Workflow was started\"}. "
                    "The Dex webhook Trigger accepts only verified POST requests with a JSON or urlencoded body up to its size limit and deduplicates by event ID, "
                    "so record each difference.")
        if note:
            self.add_finding("medium", "version-default", name, note + f" (typeVersion {version:g}; confirm against the n8n node source.)")

    # ----- graph checks -------------------------------------------------
    def adjacency(self):
        forward, backward = defaultdict(set), defaultdict(set)
        for edge in self.edges:
            forward[edge["from"]].add(edge["to"])
            backward[edge["to"]].add(edge["from"])
        return forward, backward

    def check_reachability(self) -> None:
        forward = defaultdict(set)
        for edge in self.edges:
            if edge["type"] == "main":
                forward[edge["from"]].add(edge["to"])
        reached, queue = set(), deque(node.get("name", "") for node in self.nodes if is_trigger(node))
        while True:
            while queue:
                current = queue.popleft()
                if current in reached:
                    continue
                reached.add(current)
                queue.extend(forward[current] - reached)
            # A sub-node, such as a chat model or tool, attaches to its consumer
            # through a non-main connection and runs when that consumer runs.
            attached = {
                edge["from"] for edge in self.edges
                if edge["type"] != "main" and edge["to"] in reached and edge["from"] not in reached
            }
            if not attached:
                break
            queue.extend(attached)
        for node in self.nodes:
            if short_type(node.get("type", "")) == "stickyNote":
                continue
            if node.get("name", "") not in reached:
                self.add_finding("medium", "unreachable-node", node.get("name", ""),
                                 "No trigger reaches this node, so it never runs in production; drop it and record why.")
        for node in self.nodes:
            kind = short_type(node.get("type", ""))
            if kind in ("if", "filter"):
                used = {edge["output"] for edge in self.edges if edge["from"] == node.get("name") and edge["type"] == "main"}
                for index in (0, 1):
                    if kind == "filter" and index == 1:
                        continue
                    if index not in used:
                        label = self.output_label(node.get("name", ""), "main", index)
                        self.add_finding("info", "unconnected-output", node.get("name", ""),
                                         f"The {label} output has no target; those items end silently.")

    def check_webhook_output_shape(self) -> None:
        """Webhook items wrap the request as {headers, params, query, body}; direct reads of other fields are undefined."""
        for node in self.nodes:
            if short_type(node.get("type", "")) != "webhook":
                continue
            children = {edge["to"] for edge in self.edges if edge["from"] == node.get("name") and edge["type"] == "main"}
            for expression in self.expressions:
                if expression["node"] not in children:
                    continue
                for match in re.finditer(r"\$json\.([A-Za-z_$][\w$]*)", expression["expression"]):
                    if match.group(1) not in WEBHOOK_OUTPUT_FIELDS:
                        self.add_finding("high", "webhook-output-shape", expression["node"],
                                         f"`{expression['parameter']}` reads $json.{match.group(1)}, but a Webhook item holds the request under headers, params, query, and body, so the value is undefined in n8n (did the author mean $json.body.{match.group(1)}?). Record whether Dex reproduces the undefined read or fixes it.")

    def check_branch_order(self) -> None:
        """Under executionOrder v1, n8n runs fan-out branches top to bottom by canvas position."""
        if (self.workflow.get("settings", {}) or {}).get("executionOrder", "v0") != "v1":
            return
        forward, _ = self.adjacency()
        targets_by_output = defaultdict(list)
        for edge in self.edges:
            if edge["type"] == "main":
                targets_by_output[(edge["from"], edge["output"])].append(edge["to"])
        for (source, _), targets in targets_by_output.items():
            if len(targets) < 2:
                continue
            ordered = sorted(targets, key=lambda target: tuple((self.by_name.get(target, {}).get("position") or [0, 0])[::-1]))
            self.add_finding("info", "branch-order", source,
                             f"executionOrder v1 runs these branches top to bottom on the canvas: {', '.join(ordered)}. A failure in an earlier branch stops the later ones.")
            for index, target in enumerate(ordered[:-1]):
                branch = {target} | self.descendants(target)
                waits = [name for name in branch if short_type(self.by_name.get(name, {}).get("type", "")) == "wait"]
                if waits:
                    self.add_finding("medium", "branch-wait-pause", source,
                                     f"The {target} branch contains Wait node(s) {', '.join(sorted(waits))}; n8n pauses the whole execution there, so the later branches ({', '.join(ordered[index + 1:])}) run only after the wait ends.")

    def is_multi_item_read(self, node: dict) -> bool:
        parameters = node.get("parameters", {}) or {}
        operation = str(parameters.get("operation", "")).lower()
        # A limit or returnAll parameter marks a list read even when the operation is the node default.
        is_list = operation in MULTI_ITEM_OPERATIONS or (
            self.is_app_node(node) and ("returnAll" in parameters or "limit" in parameters) and not is_trigger(node))
        return is_list and not node.get("disabled") and not self.is_effect_node(node)

    def is_effect_node(self, node: dict) -> bool:
        kind = short_type(node.get("type", ""))
        if not (self.is_app_node(node) or kind == "httpRequest") or is_trigger(node) or node.get("disabled"):
            return False
        parameters = node.get("parameters", {}) or {}
        if kind == "httpRequest":
            return str(parameters.get("method", "GET")).upper() not in ("GET", "HEAD")
        operation = str(parameters.get("operation", DEFAULT_OPERATION.get(kind, ""))).lower()
        return any(operation.startswith(verb) for verb in EFFECT_VERBS)

    def check_zero_item_stops(self) -> None:
        """A node that outputs no items stops its branch: downstream nodes do not run and the execution succeeds."""
        main_children = defaultdict(set)
        for edge in self.edges:
            if edge["type"] == "main":
                main_children[edge["from"]].add(edge["to"])
        for node in self.nodes:
            name = node.get("name", "")
            if not self.is_multi_item_read(node) or not main_children[name] or node.get("alwaysOutputData"):
                continue
            downstream = self.descendants(name)
            def handles_empty(code: str) -> bool:
                # An explicit length check, or a length read with a literal default such as `|| 'None'`.
                return bool(EMPTY_RESULT_CHECK.search(code) or (re.search(r"\.length\b", code) and re.search(r"\|\|\s*['\"`]", code)))
            fallbacks = sorted(
                other for other in downstream
                if handles_empty(str((self.by_name.get(other, {}).get("parameters", {}) or {}).get("jsCode", "")))
            )
            message = (f"When this read returns no items, n8n runs none of {', '.join(sorted(main_children[name]))} or anything after them, "
                       "and the execution still succeeds. A Dex Flow that continues with an empty list changes the effects; record which behavior Dex keeps.")
            if fallbacks:
                message += f" The empty-result handling in {', '.join(fallbacks)} never runs in n8n (dead code unless alwaysOutputData is on)."
            self.add_finding("high" if fallbacks else "medium", "zero-items-stop", name, message)

    def check_repeated_effects(self) -> None:
        """A schedule that fires more often than its read window repeats the same effects every execution."""
        for schedule in self.schedules:
            if schedule.get("field") not in ("seconds", "minutes", "hours"):
                continue
            downstream = self.descendants(schedule["node"], "main")
            # A whole-day window counts only where a read node uses it, not where an effect merely prints the date.
            windowed = sorted({
                expression["node"] for expression in self.expressions
                if expression["node"] in downstream and DAY_WINDOW.search(expression["expression"])
                and not self.is_effect_node(self.by_name.get(expression["node"], {}))
                and (self.is_app_node(self.by_name.get(expression["node"], {})) or short_type(self.by_name.get(expression["node"], {}).get("type", "")) == "httpRequest")
            })
            effects = sorted({name for read in windowed for name in self.descendants(read, "main") if self.is_effect_node(self.by_name.get(name, {}))})
            if windowed and effects:
                self.add_finding("high", "repeated-effects", schedule["node"],
                                 f"The schedule fires {schedule['description']}, but {', '.join(windowed)} read a whole-day window, so every execution repeats "
                                 f"{', '.join(effects)} for the same items; n8n keeps no memory between executions. Record the repetition as source behavior and ask whether Dex keeps it.")
                return

    def check_secret_requests(self) -> None:
        """A credential that travels from workflow data into a request belongs to the connector connection."""
        for expression in self.expressions:
            node = self.by_name.get(expression["node"], {})
            if not (short_type(node.get("type", "")) == "httpRequest" or self.is_app_node(node)) or node.get("disabled"):
                continue
            parameter = expression["parameter"].lower()
            fields = set(re.findall(r"(?:\$json|\.json)\.([A-Za-z_$][\w$]*)", expression["expression"]))
            secrets = sorted(field for field in fields
                             if field in self.secret_fields or (CREDENTIAL_FIELD.search(field) and not NON_CREDENTIAL_FIELD.search(field)))
            if not secrets:
                continue
            where = "URL" if re.split(r"[.\[]", parameter)[-1] == "url" or "queryparameters" in parameter else "request"
            self.add_finding("high", "secret-in-request", expression["node"],
                             f"`{expression['parameter']}` sends the credential field(s) {', '.join(f'`{field}`' for field in secrets)} from workflow data in the {where}"
                             + (", where provider, proxy, and n8n logs record it" if where == "URL" else "")
                             + ". In Dex the credential belongs to the connector connection, sent as its manifest declares; record the divergence.")

    def check_model_output_bodies(self) -> None:
        """Email bodies built from model output carry whatever markup the model returns."""
        model_nodes = {
            node.get("name", "") for node in self.nodes
            if "langchain" in node.get("type", "") and short_type(node.get("type", "")).startswith(LANGCHAIN_ROOT_PREFIXES)
        }
        if not model_nodes:
            return
        for expression in self.expressions:
            node = self.by_name.get(expression["node"], {})
            if short_type(node.get("type", "")) not in EMAIL_NODE_TYPES:
                continue
            if re.split(r"[.\[]", expression["parameter"])[-1] not in MESSAGE_BODY_PARAMETERS:
                continue
            sources = (set(expression["references"]) | self.ancestors(expression["node"])) & model_nodes
            if sources:
                self.add_finding("medium", "model-output-body", expression["node"],
                                 f"`{expression['parameter']}` sends output of {', '.join(sorted(sources))} as the message body without escaping or validation; provider text that reached the model can add markup or links. Port it as is, then decide escaping or an allowlist explicitly.")

    def check_merge_inputs(self) -> None:
        for node in self.nodes:
            if short_type(node.get("type", "")) != "merge":
                continue
            name = node.get("name", "")
            parameters = node.get("parameters", {}) or {}
            inputs = int(parameters.get("numberInputs", 2) or 2)
            unreachable = {item["node"] for item in self.findings if item["kind"] == "unreachable-node"}
            for index in range(inputs):
                feeders = [edge["from"] for edge in self.edges if edge["to"] == name and edge["type"] == "main" and edge.get("input", 0) == index]
                live = [feeder for feeder in feeders if feeder not in unreachable]
                if not live:
                    detail = f"is fed only by unreachable {', '.join(feeders)}" if feeders else "has no connection"
                    mode = parameters.get("mode", "append")
                    if mode == "chooseBranch" and index < 2:
                        outcome = "Choose-branch requires inputs 1 and 2, so under executionOrder v1 the Merge and everything after it never run, and the execution ends without an error."
                    else:
                        outcome = f"Mode {mode} runs with that input empty under executionOrder v1; confirm at typeVersion {node_version(node):g}."
                    self.add_finding("high", "merge-input", name, f"Merge input {index + 1} {detail}, so it never receives items in production. {outcome}")

    def check_wait_loops(self) -> None:
        for node in self.nodes:
            if short_type(node.get("type", "")) != "wait":
                continue
            name = node.get("name", "")
            if name in self.descendants(name):
                cycle = sorted(other for other in self.descendants(name) if name in self.descendants(other))
                if any(short_type(self.by_name.get(other, {}).get("type", "")) == "splitInBatches" for other in cycle):
                    self.add_finding("info", "wait-rate-limit", name,
                                     f"This Wait paces a Loop Over Items batch loop ({', '.join(cycle)}): a rate limit, not polling. Map it to batched Steps with a Timer between batches.")
                    continue
                self.add_finding("medium", "wait-poll-loop", name,
                                 f"This Wait sits in a loop ({', '.join(cycle)}): a fixed delay standing in for an external job finishing. Map the loop to the Dex Polling pattern with a bounded attempt count, not a Timer plus a jump back, and record the source's missing bound if it has none.")

    def check_preflight(self) -> None:
        """n8n refuses to start an execution while a main-reachable node lacks a required displayed parameter."""
        hollow = {item["node"] for item in self.findings if item["kind"] == "hollow-node" and "missing required" in item["message"]}
        triggers = [node.get("name", "") for node in self.nodes if is_trigger(node) and not node.get("disabled")]
        failing = {}
        for trigger in triggers:
            reachable = {trigger} | self.descendants(trigger, "main")
            blocking = sorted(name for name in hollow & reachable if not langchain_sub_node_role(self.by_name.get(name, {})))
            if blocking:
                failing[trigger] = blocking
        if not failing:
            return
        scope = ("for any trigger event" if len(failing) == len(triggers)
                 else f"for executions started by {', '.join(sorted(failing))}; executions from other triggers still run")
        nodes = sorted({name for names in failing.values() for name in names})
        self.add_finding("high", "preflight-fails", "(workflow)",
                         "Before the first node runs, n8n checks every enabled node reachable from the starting trigger for empty required parameters that are displayed at its version, "
                         f"and fails the whole execution if one is empty. If {', '.join(nodes)} lack such a parameter, the exported workflow has no effect {scope}. "
                         "Confirm each parameter in the node source, record that effect as none, and do not offer a 'faithful' option that assumes later nodes run. Credentials are not part of this check.")

    def check_open_triggers(self) -> None:
        for node in self.nodes:
            kind = short_type(node.get("type", ""))
            parameters = node.get("parameters", {}) or {}
            if kind == "telegramTrigger":
                fields = parameters.get("additionalFields", {}) or {}
                restricted = node_version(node) >= 1.2 and (fields.get("chatIds") or fields.get("userIds"))
                if not restricted:
                    self.add_finding("high", "open-trigger", node.get("name", ""),
                                     "The Telegram Trigger starts the workflow for anyone who messages the bot: chat and user restrictions are absent or ignored before typeVersion 1.2. "
                                     "Record the open trigger as source behavior and ask whether Dex keeps it or filters senders.")

    def check_provenance(self) -> None:
        meta = self.workflow.get("meta") or {}
        reasons = []
        if meta.get("templateId"):
            reasons.append(f"meta.templateId {meta['templateId']} marks a gallery template")
        if self.workflow.get("triggerCount") == 0:
            reasons.append("triggerCount 0 means no trigger was ever active")
        if self.workflow.get("active") is False:
            reasons.append("active is false")
        if reasons:
            self.add_finding("info", "provenance", "(workflow)",
                             "; ".join(reasons) + ". Treat the export as a specification that may never have run: there may be no execution history to compare, so accept against user-approved expected effects on synthetic inputs.")

    def check_authentication_consistency(self) -> None:
        methods = defaultdict(set)
        for node in self.nodes:
            if self.is_app_node(node) and not is_trigger(node):
                methods[short_type(node.get("type", ""))].add(str((node.get("parameters", {}) or {}).get("authentication", "default")))
        for kind, values in methods.items():
            if len(values) > 1:
                self.add_finding("medium", "inconsistent-authentication", f"{kind} nodes",
                                 f"{kind} nodes use different authentication settings ({', '.join(sorted(values))}); confirm whether they act for one account (one Dex connection) or several.")

    def descendants(self, name: str, connection_type: str = "") -> set:
        forward = defaultdict(set)
        for edge in self.edges:
            if not connection_type or edge["type"] == connection_type:
                forward[edge["from"]].add(edge["to"])
        seen, queue = set(), deque(forward[name])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            queue.extend(forward[current] - seen)
        return seen

    def ancestors(self, name: str) -> set:
        _, backward = self.adjacency()
        seen, queue = set(), deque(backward[name])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            queue.extend(backward[current] - seen)
        return seen

    def check_references(self) -> None:
        for expression in self.expressions:
            for reference in expression["references"]:
                if reference not in self.by_name:
                    self.add_finding("high", "missing-node-reference", expression["node"],
                                     f"`{expression['parameter']}` reads node {reference!r}, which is not in the export.")
                elif reference not in self.ancestors(expression["node"]):
                    self.add_finding("high", "non-ancestor-reference", expression["node"],
                                     f"`{expression['parameter']}` reads node {reference!r}, which is not upstream; n8n fails or reads stale data. Resolve the intended source.")

    def check_dead_fields(self) -> None:
        texts = defaultdict(list)
        for expression in self.expressions:
            texts[expression["node"]].append(expression["expression"])
        for node in self.nodes:
            parameters = node.get("parameters", {}) or {}
            code = parameters.get("jsCode") or parameters.get("functionCode") or ""
            if code:
                texts[node.get("name", "")].append(code)
        for field in self.set_fields:
            name = field["name"]
            if not name:
                continue
            pattern = re.compile(r"(?:\.|\[\s*['\"])" + re.escape(name) + r"\b")
            used = any(
                pattern.search(text)
                for node_name, node_texts in texts.items()
                if node_name != field["node"]
                for text in node_texts
            )
            if not used:
                self.add_finding("medium", "dead-config", field["node"],
                                 f"Field `{name}` is never read explicitly downstream. Confirm that no node consumes whole items, then drop it or wire it as intended.")

    def check_literal_sets(self) -> None:
        forward, _ = self.adjacency()
        for node in self.nodes:
            if short_type(node.get("type", "")) not in ("if", "filter"):
                continue
            accepted = set()
            for condition in (node.get("parameters", {}).get("conditions", {}) or {}).get("conditions", []) or []:
                operation = condition.get("operator", {}).get("operation", "")
                right = condition.get("rightValue")
                if operation in ("startsWith", "equals", "contains") and isinstance(right, str) and right:
                    accepted.add(right.lower())
            if not accepted:
                continue
            descendants, queue = set(), deque(forward[node.get("name", "")])
            while queue:
                current = queue.popleft()
                if current in descendants:
                    continue
                descendants.add(current)
                queue.extend(forward[current] - descendants)
            for expression in self.expressions:
                if expression["node"] not in descendants:
                    continue
                stripped = {match.group(2).lower() for match in STRING_REPLACE.finditer(expression["expression"])}
                if not stripped:
                    continue
                unhandled = sorted(accepted - stripped)
                unused = sorted(stripped - accepted)
                if unhandled:
                    self.add_finding("high", "literal-set-mismatch", expression["node"],
                                     f"`{node.get('name')}` accepts {sorted(accepted)}, but `{expression['parameter']}` strips only {sorted(stripped)}: values matching {unhandled} pass the filter unnormalized"
                                     + (f", and the filter never accepts {unused} on its own, so that strip only changes values that also match an accepted literal." if unused else "."))

    def check_settings(self) -> None:
        settings = self.workflow.get("settings", {}) or {}
        if not settings.get("timezone"):
            if any(item["kind"] in ("timezone-dependent", "version-default") and "timezone" in item["message"] for item in self.findings) or self.schedules:
                self.add_finding("high", "timezone-unset", "(workflow)",
                                 "settings.timezone is absent, so schedules, $today, and $now use the n8n instance's GENERIC_TIMEZONE, which is America/New_York when the instance never set it. The export cannot tell which zone; ask the user.")
        if settings.get("errorWorkflow"):
            self.add_finding("high", "error-workflow", "(workflow)",
                             "An error workflow handles failures; map it to Execute-failure recovery Steps.")
        if self.workflow.get("pinData"):
            self.add_finding("info", "pin-data", "(workflow)",
                             "pinData holds editor test data, not production behavior; it may contain personal data. Use it only to shape synthetic fixtures.")

    # ----- plan drafts --------------------------------------------------
    def connector_matrix(self) -> list[dict]:
        """Match each integration node to candidate released connectors and operations."""
        rows = []
        for node in self.nodes:
            kind = short_type(node.get("type", ""))
            is_http = kind == "httpRequest"
            if not (is_http or (self.is_app_node(node) and kind != "stickyNote") or "langchain" in node.get("type", "")):
                continue
            parameters = node.get("parameters", {}) or {}
            operation = str(parameters.get("operation", DEFAULT_OPERATION.get(kind, "")))
            resource = str(parameters.get("resource", DEFAULT_RESOURCE.get(kind, "")))
            row = {"node": node.get("name", ""), "type": kind, "operation": "/".join(part for part in (resource, operation) if part),
                   "host": "", "connector": "", "operations": [], "likelyOperation": "", "semanticNote": "", "status": ""}
            sub_node_role = langchain_sub_node_role(node)
            if sub_node_role:
                row["status"] = sub_node_role
                rows.append(row)
                continue
            candidates = list(N8N_CONNECTOR_CANDIDATES.get(kind, []))
            if is_http:
                row["host"] = http_request_host(parameters.get("url", ""))
                label = row["host"].split(".")[-2] if row["host"].count(".") >= 1 else row["host"]
                candidates = [entry["id"] for entry in self.catalog or [] if label and label in catalog_search_text(entry)]
            elif not candidates and self.catalog:
                candidates = [entry["id"] for entry in self.catalog if kind.lower().replace("trigger", "") in catalog_search_text(entry)]
            if self.catalog is None:
                row["connector"] = ", ".join(candidates) or "-"
                row["status"] = "catalog not provided; pass --catalog"
            else:
                released = [entry for candidate in candidates for entry in self.catalog if entry["id"] == candidate]
                if released:
                    entry = released[0]
                    row["connector"] = f"{entry['id']} {entry['version']}"
                    row["operations"] = [f"{name} ({op_kind})" for name, op_kind in entry["operations"]] + [f"{name} (trigger)" for name in entry["triggers"]]
                    row["likelyOperation"] = likely_operation(operation, entry)
                    verb = re.sub(r"[^a-z]", "", operation.split("/")[-1].lower())
                    if row["likelyOperation"] and verb and not row["likelyOperation"].lower().startswith(verb[:4]):
                        row["semanticNote"] = f"semantics differ from n8n {verb}: confirm and record a divergence"
                    row["status"] = "released candidate; confirm the exact operation in its connector.yaml"
                elif is_http and not row["host"]:
                    row["status"] = "the URL host comes from an expression: resolve the host from upstream data before choosing a connector"
                elif is_http:
                    row["status"] = f"no released connector for {row['host']}: connector contribution (generic HTTP only for an internal service)"
                else:
                    row["status"] = "no released connector: connector contribution"
            rows.append(row)
        return rows

    def plan_rows(self) -> list[dict]:
        """Draft one Dex element per node, in execution order from the triggers."""
        forward, _ = self.adjacency()
        matrix = {row["node"]: row for row in self.connector_matrix()}
        order, seen = [], set()
        queue = deque(node.get("name", "") for node in self.nodes if is_trigger(node))
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            order.append(current)
            queue.extend(sorted(forward[current] - seen))
        for edge in self.edges:
            if edge["type"] != "main" and edge["from"] not in seen and edge["to"] in order:
                order.insert(order.index(edge["to"]) + 1, edge["from"])
                seen.add(edge["from"])
        order += [node.get("name", "") for node in self.nodes if node.get("name", "") not in seen]
        unreachable = {item["node"] for item in self.findings if item["kind"] == "unreachable-node"}
        multi_item_sources = {
            node.get("name", "") for node in self.nodes
            if str((node.get("parameters", {}) or {}).get("operation", "")).lower() in MULTI_ITEM_OPERATIONS
        }
        rows = []
        for name in order:
            node = self.by_name.get(name, {})
            kind = short_type(node.get("type", ""))
            per_item = any(source in self.ancestors(name) for source in multi_item_sources)
            if kind == "stickyNote" or kind == "noOp":
                element, notes = "dropped", "no behavior"
            elif name in unreachable:
                element, notes = "dropped", "unreachable: never runs in production"
            elif node.get("disabled"):
                element, notes = "dropped", "disabled: n8n passes its items through unchanged"
            elif kind == "set":
                element, notes = "folded into the consuming Step", self.hint(node)
            elif kind in ("if", "filter", "switch"):
                element, notes = "folded into an application Step", "the predicate chooses that Step's movement; port it with the IF semantics in n8n-semantics"
            elif kind == "wait":
                element = f"application Step {pascal_case(name)}"
                resume = (node.get("parameters", {}) or {}).get("resume", "timeInterval")
                if resume in ("webhook", "form"):
                    notes = "WaitFor waits on a Channel or typed RPC resume, plus a Timer only if limitWaitTime is set; Execute builds the next Step's input"
                else:
                    notes = "WaitFor returns dex.Until(dex.Timer(duration)); Execute builds the next Step's input (a Connector Step cannot wait)"
            elif is_trigger(node):
                element, notes = "trigger", self.hint(node)
            elif langchain_sub_node_role(node):
                element, notes = "configuration", langchain_sub_node_role(node)
            elif name in matrix:
                connector = matrix[name]
                element = f"Connector Step {pascal_case(name)}"
                notes = f"{connector['connector'] or 'missing connector'}: {connector['likelyOperation'] or connector['status']}"
                if connector.get("semanticNote"):
                    notes += f"; {connector['semanticNote']}"
                if per_item:
                    notes += "; per item: loop with a persisted cursor (a Connector result carries no item context)"
                predecessors = {edge["from"] for edge in self.edges if edge["to"] == name and edge["type"] == "main"}
                if any(predecessor in matrix and not langchain_sub_node_role(self.by_name.get(predecessor, {})) for predecessor in predecessors):
                    notes += "; add an application Step before it: a Connector Step receives only the previous result, so map the input and persist context there"
                notes += "; route every branch in its connector.yaml (an unrouted optional branch fails the Flow) and an Execute-failure route; add an outcome application Step when the next Step needs more than the result"
                successors = {edge["to"] for edge in self.edges if edge["from"] == name and edge["type"] == "main"}
                if len(successors) > 1:
                    notes += "; fan-out: put an application Step after it, since only application Steps move to several Steps"
            else:
                element = f"application Step {pascal_case(name)}"
                notes = self.hint(node)
            rows.append({"node": name, "type": kind, "element": element, "notes": notes})
        return rows

    def to_mermaid(self) -> list[str]:
        ids = {}
        lines = ["```mermaid", "flowchart LR"]
        for index, node in enumerate(node for node in self.nodes if short_type(node.get("type", "")) != "stickyNote"):
            ids[node.get("name", "")] = f"n{index + 1}"
            label = (node.get("name", "") + "<br/>" + short_type(node.get("type", ""))).replace('"', "#quot;")
            lines.append(f'  n{index + 1}["{label}"]')
        for edge in self.edges:
            if edge["from"] in ids and edge["to"] in ids:
                arrow = f" -- {edge['label']} --> " if edge["label"] not in ("main",) else " --> "
                lines.append(f"  {ids[edge['from']]}{arrow}{ids[edge['to']]}")
        lines.append("```")
        return lines

    # ----- output -------------------------------------------------------
    def to_json(self) -> dict:
        settings = self.workflow.get("settings", {}) or {}
        data = {
            "workflow": {"name": self.workflow.get("name", ""), "source": self.source_name, "settings": settings},
            "nodes": self.node_rows,
            "edges": self.edges,
            "expressions": self.expressions,
            "setFields": self.set_fields,
            "schedules": self.schedules,
            "credentials": [
                {"type": key[0], "name": key[1], "nodes": nodes} for key, nodes in self.credentials.items()
            ],
            "claims": self.claims,
            "findings": self.findings,
            "connectorMatrix": self.connector_matrix(),
            "planDraft": self.plan_rows(),
            "ledgerIds": self.ledger_ids or [cells[0] for _, cells in ledger_rows(self.to_markdown())],
        }
        return json.loads(self.redact(json.dumps(data)))

    def redact(self, text: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(secret, "‹redacted›")
            text = text.replace(json.dumps(secret)[1:-1], "‹redacted›")
        return text

    def to_markdown(self) -> str:
        lines = []
        name = self.workflow.get("name", "(unnamed workflow)")
        counts = {severity: sum(1 for item in self.findings if item["severity"] == severity) for severity in SEVERITY_ORDER}
        triggers = [row for row in self.node_rows if is_trigger(self.by_name[row["node"]])]
        code_nodes = [row for row in self.node_rows if row["type"].split("@")[0] in ("code", "function", "functionItem")]
        integrations = [
            row for row in self.node_rows
            if row["type"].split("@")[0] == "httpRequest"
            or (self.is_app_node(self.by_name[row["node"]]) and not is_trigger(self.by_name[row["node"]]))
        ]
        lines += [
            f"# n8n → Dex import ledger: {name}",
            "",
            f"Source `{self.source_name}`: {len(self.nodes)} nodes, {len(self.edges)} connections. "
            "Generated by `n8n_inventory.py`; literal secrets are redacted.",
            "",
            "Set every Status cell to `mapped`, `diverged`, `dropped`, `blocked`, or `pending`. "
            "Use `pending` for a proposal that still awaits the user's decision, and `diverged` only once the user approved it. "
            "Every status except `mapped` needs Notes that record the reason or the decision. "
            "Then run `n8n_inventory.py verify` on this file; `--strict` also fails while anything is pending.",
            "",
            "## Summary",
            "",
            f"- Triggers: {', '.join(row['node'] + ' (' + row['type'] + ')' for row in triggers) or 'none'}",
            f"- Integrations: {', '.join(row['node'] + ' (' + row['type'] + ')' for row in integrations) or 'none'}",
            f"- Code nodes: {', '.join(row['node'] for row in code_nodes) or 'none'}",
            f"- Findings: {counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['info']} info",
            "",
            "Rows may be split into sub-rows (`N3a`, `N3b`) when parts of one element map differently. "
            "Add rows found during the semantic review with the next free ID in their section.",
            "",
            "## Execution graph",
            "",
            "| ID | From | Output | To | Status | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for index, edge in enumerate(self.edges, 1):
            lines.append(f"| E{index} | {cell(edge['from'])} | {cell(edge['label'])} | {cell(edge['to'])} | todo |   |")
        lines += ["", "Compare this graph with the Dex Web rendering of the migrated Flows.", ""]
        lines += self.to_mermaid()
        lines += ["", "## Nodes", "", "| ID | Node | Type | Source behavior | Dex mapping hint | Status | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for index, row in enumerate(self.node_rows, 1):
            lines.append(f"| N{index} | {cell(row['node'])} | {cell(row['type'])} | {cell(row['behavior'], 320)} | {cell(row['hint'])} | todo |   |")
        lines += ["", "## Expressions", "", "| ID | Node | Parameter | Expression | Semantics to preserve | Status | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for index, expression in enumerate(self.expressions, 1):
            lines.append(
                f"| X{index} | {cell(expression['node'])} | {cell(expression['parameter'])} | {cell(expression['expression'], 260)} | "
                f"{cell('; '.join(expression['semantics']) or 'plain value', 260)} | todo |   |"
            )
        lines += ["", "## Credentials", "", "| ID | n8n credential | Used by | Dex connection | Status | Notes |", "| --- | --- | --- | --- | --- | --- |"]
        for index, (key, nodes) in enumerate(self.credentials.items(), 1):
            lines.append(
                f"| C{index} | {cell(key[0])} `{cell(key[1])}` | {cell(', '.join(nodes))} | "
                "Connector connection authorized in Dex Web Connectors; n8n credentials are not portable | todo |   |"
            )
        credential_index = len(self.credentials)
        uncredentialed = defaultdict(list)
        for row in self.connector_matrix():
            node = self.by_name.get(row["node"], {})
            if not node.get("credentials") and self.is_app_node(node) and not node.get("disabled"):
                connector = row["connector"] if row["connector"] and row["connector"] != "-" else row["type"]
                uncredentialed[connector].append(row["node"])
        for connector, nodes in uncredentialed.items():
            credential_index += 1
            lines.append(f"| C{credential_index} | (none in the export) | {cell(', '.join(nodes))} | "
                         f"A Dex connection is still needed for {cell(connector)}; ask which account it acts for | todo |   |")
        settings = self.workflow.get("settings", {}) or {}
        lines += ["", "## Connector branches", "",
                  "Replace each placeholder with one row per branch of the mapped operation, read from its connector.yaml at the release tag, "
                  "and say where each branch goes and which source outcome it matches.", "",
                  "| ID | n8n node | Branch and Dex target | Status | Notes |", "| --- | --- | --- | --- | --- |"]
        branch_nodes = [row["node"] for row in self.connector_matrix()
                        if not langchain_sub_node_role(self.by_name.get(row["node"], {})) and not is_trigger(self.by_name.get(row["node"], {}))
                        and not self.by_name.get(row["node"], {}).get("disabled")
                        and row["node"] not in {item["node"] for item in self.findings if item["kind"] == "unreachable-node"}]
        for index, node_name in enumerate(branch_nodes, 1):
            lines.append(f"| R{index} | {cell(node_name)} | {BRANCH_PLACEHOLDER} | todo |   |")
        lines += ["", "## Workflow settings and export metadata", "", "| ID | Setting | Value | Status | Notes |", "| --- | --- | --- | --- | --- |"]
        setting_rows = [("timezone", settings.get("timezone", "(absent: instance default)"))]
        setting_rows += [(key, value) for key, value in settings.items() if key != "timezone"]
        meta = self.workflow.get("meta") or {}
        for key in ("active", "triggerCount"):
            if key in self.workflow:
                setting_rows.append((key, self.workflow[key]))
        for key, value in meta.items():
            setting_rows.append((f"meta.{key}", value if key != "instanceId" else "(present)"))
        for key in ("pinData", "staticData"):
            if self.workflow.get(key):
                setting_rows.append((key, "(present: editor or trigger state, not behavior)"))
        for index, (key, value) in enumerate(setting_rows, 1):
            lines.append(f"| S{index} | {cell(key)} | {cell(json.dumps(value) if not isinstance(value, str) else value)} | todo |   |")
        lines += ["", "## Findings", "", "| ID | Severity | Kind | Node | Finding | Status | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for index, finding in enumerate(self.findings, 1):
            lines.append(
                f"| F{index} | {finding['severity']} | {finding['kind']} | {cell(finding['node'])} | {cell(finding['message'], 420)} | todo |   |"
            )
        lines += ["", "## Behavior matrix", "",
                  "What the source does in each situation; Dex must match it or record a decision.", "",
                  "| ID | Situation | Nodes | n8n behavior | Status | Notes |", "| --- | --- | --- | --- | --- | --- |"]
        for index, row in enumerate(self.behavior_rows(), 1):
            lines.append(f"| B{index} | {cell(row[0])} | {cell(row[1])} | {cell(row[2], 320)} | todo |   |")
        lines += ["", "## Claims to check against behavior", "",
                  "| ID | Source | Claim | Status | Notes |", "| --- | --- | --- | --- | --- |"]
        for index, claim in enumerate(self.claims, 1):
            lines.append(f"| K{index} | {cell(claim['source'])} | {cell(claim['text'], 400)} | todo |   |")
        lines += ["", "## Connector capability matrix (draft)", "",
                  "Confirm each candidate in the connector's release-tagged `connector.yaml` before mapping a row.", "",
                  "| n8n node | Type and operation | Candidate connector | Likely operation | Released operations and Triggers | Status |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for row in self.connector_matrix():
            operation = row["operation"] + (f" ({row['host']})" if row["host"] else "")
            likely = row["likelyOperation"] + (f" ({row['semanticNote']})" if row["semanticNote"] else "")
            lines.append(f"| {cell(row['node'])} | {cell(row['type'] + ' ' + operation)} | {cell(row['connector'] or '-')} | "
                         f"{cell(likely or '-')} | {cell(', '.join(row['operations']) or '-', 300)} | {cell(row['status'])} |")
        lines += ["", "## Dex plan draft", "",
                  "A starting point in execution order. Apply the Flow-boundary, schedule, and per-item rules before coding.", "",
                  "| Order | n8n node | Type | Proposed Dex element | Notes |", "| --- | --- | --- | --- | --- |"]
        for index, row in enumerate(self.plan_rows(), 1):
            lines.append(f"| {index} | {cell(row['node'])} | {cell(row['type'])} | {cell(row['element'])} | {cell(row['notes'], 320)} |")
        decisions = defaultdict(list)
        for index, finding in enumerate(self.findings, 1):
            if finding["severity"] in ("critical", "high"):
                decisions[finding["kind"]].append((index, finding))
        lines += ["", "## Decisions for the user", "",
                  "One row per kind of open question. Set Status to `decided` with the user's answer in Notes, or `pending` while it is open.", "",
                  "| ID | Kind | Findings | Question | Status | Notes |", "| --- | --- | --- | --- | --- | --- |"]
        for index, (kind, items) in enumerate(decisions.items(), 1):
            ids = ", ".join(f"F{number}" for number, _ in items)
            question = items[0][1]["message"] if len(items) == 1 else f"{len(items)} findings on {', '.join(sorted({item['node'] for _, item in items}))}: {items[0][1]['message']}"
            lines.append(f"| D{index} | {kind} | {ids} | {cell(question, 420)} | todo |   |")
        if not decisions:
            lines.append("| D1 | none | - | No critical or high finding; add questions found during the semantic review. | todo |   |")
        lines.append("")
        rendered = self.redact("\n".join(lines))
        self.ledger_ids = [cells[0] for _, cells in ledger_rows(rendered)]
        return rendered

    def behavior_rows(self) -> list[tuple]:
        rows = []
        for node in self.nodes:
            if self.is_multi_item_read(node):
                kept = "alwaysOutputData emits one empty item, so downstream still runs" if node.get("alwaysOutputData") else "downstream nodes do not run and the execution succeeds"
                rows.append(("Read returns zero items", node.get("name", ""), kept))
        external = [node for node in self.nodes if (self.is_app_node(node) or short_type(node.get("type", "")) == "httpRequest")
                    and not is_trigger(node) and not node.get("disabled")]
        if external:
            handled = [node.get("name", "") for node in external if (node.get("onError") or "stopWorkflow") != "stopWorkflow" or node.get("continueOnFail")]
            retried = [node.get("name", "") for node in external if node.get("retryOnFail")]
            detail = "the node fails and the execution stops; earlier effects stay done"
            if retried:
                detail += f"; {', '.join(retried)} retry first"
            if handled:
                detail += f"; {', '.join(handled)} continue per onError"
            rows.append(("Provider error, timeout, or rejection", ", ".join(node.get("name", "") for node in external), detail))
        for node in self.nodes:
            if is_trigger(node):
                kind = short_type(node.get("type", ""))
                detail = {
                    "webhook": "every request starts its own execution; n8n does not deduplicate retries or double submits",
                    "scheduleTrigger": "every occurrence starts an execution, even while the previous one still runs; missed occurrences while n8n is down do not run",
                    "manualTrigger": "every click starts an execution",
                }.get(kind, "every delivered event starts its own execution unless the trigger node deduplicates; confirm in the node source")
                rows.append(("Duplicate or overlapping trigger", node.get("name", ""), detail))
        if self.expressions:
            rows.append(("Input item lacks a field an expression reads", "expressions X1 onward",
                         "an expression yields undefined, and a method call on the missing value is swallowed, so the value is empty and the node continues; "
                         "a strict IF accepts null and undefined; Code nodes throw instead"))
        return rows


def langchain_sub_node_role(node: dict) -> str:
    """Describe a LangChain sub-node's role in its consumer, or return an empty string."""
    if "langchain" not in node.get("type", ""):
        return ""
    kind = short_type(node.get("type", ""))
    for prefix, role in LANGCHAIN_SUB_NODE_PREFIXES.items():
        if kind.startswith(prefix):
            return role
    return ""


def http_request_host(url) -> str:
    """Return the host of the literal part of an HTTP Request URL, or an empty string."""
    if not isinstance(url, str):
        return ""
    literal = url[1:] if url.startswith("=") else url
    match = re.match(r"\s*(?:https?://)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})", literal)
    return match.group(1).lower() if match else ""


def catalog_search_text(entry: dict) -> str:
    return re.sub(r"[^a-z0-9]", "", " ".join((entry["id"], entry["name"], entry["company"])).lower())


def likely_operation(operation: str, entry: dict) -> str:
    verb = re.sub(r"[^a-z]", "", operation.split("/")[-1].lower())
    for prefix in OPERATION_VERBS.get(verb, [verb] if verb else []):
        for name, _ in entry["operations"]:
            if name.lower().startswith(prefix):
                return name
    return ""


def pascal_case(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    return "".join(word[:1].upper() + word[1:] for word in words) or "Step"


def load_catalog(path: Path) -> list:
    """Read the published connector catalog's connector IDs, versions, Triggers, and operations.

    The catalog is generated YAML with a fixed shape, so a line reader suffices and keeps the
    script free of third-party packages.
    """
    text = path.read_text(encoding="utf-8")
    if "kind: ConnectorCatalog" not in text or not re.search(r"^apiVersion: connectors\.dex\.dev/catalog/", text, re.MULTILINE):
        raise ValueError(f"{path} is not a Dex connector catalog (expected apiVersion connectors.dex.dev/catalog/* and kind ConnectorCatalog)")
    entries, current, section, pending_operation = [], None, "", None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 4 and stripped.startswith("- company:"):
            current = {"id": "", "name": "", "company": stripped.split(":", 1)[1].strip(), "version": "", "triggers": [], "operations": []}
            entries.append(current)
            section, pending_operation = "", None
            continue
        if current is None:
            continue
        if indent == 6 and ":" in stripped and not stripped.startswith("- "):
            key, value = (part.strip() for part in stripped.split(":", 1))
            if key in ("id", "name", "version"):
                current[key] = value
            section = key if key in ("triggers", "operations", "uiUnits") else section if key == "" else key
            continue
        if indent == 8 and stripped.startswith("- name:"):
            name = stripped.split(":", 1)[1].strip()
            if section == "triggers":
                current["triggers"].append(name)
            elif section == "operations":
                pending_operation = [name, ""]
                current["operations"].append(pending_operation)
            continue
        if indent == 10 and stripped.startswith("kind:") and section == "operations" and pending_operation is not None:
            pending_operation[1] = stripped.split(":", 1)[1].strip()
    for entry in entries:
        entry["operations"] = [tuple(operation) for operation in entry["operations"]]
    return [entry for entry in entries if entry["id"]]


def describe_schedule_rule(rule: dict) -> dict:
    field = rule.get("field", "days")
    minute = int(rule.get("triggerAtMinute", 0) or 0)
    hour = int(rule.get("triggerAtHour", 0) or 0)
    if field == "seconds":
        interval = rule.get("secondsInterval", 30)
        return {"field": field, "description": f"every {interval} seconds", "cron": f"*/{interval} * * * * *", "hour": None}
    if field == "minutes":
        interval = rule.get("minutesInterval", 5)
        return {"field": field, "description": f"every {interval} minutes", "cron": f"*/{interval} * * * *", "hour": None}
    if field == "hours":
        interval = rule.get("hoursInterval", 1)
        every = "every hour" if interval == 1 else f"every {interval} hours"
        return {"field": field, "description": f"{every} at minute {minute}", "cron": f"{minute} */{interval} * * *", "hour": None}
    if field == "days":
        interval = rule.get("daysInterval", 1)
        every = "every day" if interval == 1 else f"every {interval} days"
        return {"field": field, "description": f"{every} at {hour:02d}:{minute:02d}", "cron": f"{minute} {hour} * * *" if interval == 1 else "", "hour": hour}
    if field == "weeks":
        days = rule.get("triggerAtDay", [])
        return {"field": field, "description": f"every {rule.get('weeksInterval', 1)} week(s) on weekday(s) {days or 'default'} at {hour:02d}:{minute:02d}", "cron": "", "hour": hour}
    if field == "months":
        return {"field": field, "description": f"every {rule.get('monthsInterval', 1)} month(s) on day {rule.get('triggerAtDayOfMonth', 1)} at {hour:02d}:{minute:02d}", "cron": "", "hour": hour}
    if field == "cronExpression":
        expression = rule.get("expression", "")
        return {"field": field, "description": f"cron `{expression}`", "cron": expression, "hour": None}
    return {"field": field, "description": f"unrecognized rule {json.dumps(rule)}", "cron": "", "hour": None}


def schedule_label_mismatch(label: str, rule: dict):
    text = label.lower()
    field = rule.get("field", "")
    daily = re.search(r"\b(daily|every\s+(day|morning|evening|night)|each\s+(day|morning)|morning|nightly)\b", text)
    hourly = re.search(r"\b(hourly|every\s+hour)\b", text)
    weekly = re.search(r"\b(weekly|every\s+week)\b", text)
    hour_match = re.search(r"@\s*(\d{1,2})(?::\d{2})?\s*(am|pm)?|\b(\d{1,2})(?::\d{2})?\s*(am|pm)\b", text)
    if daily and field in ("seconds", "minutes", "hours"):
        return daily.group(0)
    if hourly and field != "hours":
        return hourly.group(0)
    if weekly and field in ("seconds", "minutes", "hours", "days"):
        return weekly.group(0)
    if hour_match:
        hour = int(hour_match.group(1) or hour_match.group(3))
        suffix = hour_match.group(2) or hour_match.group(4)
        if suffix == "pm" and hour < 12:
            hour += 12
        if field in ("seconds", "minutes", "hours"):
            return hour_match.group(0).strip()
        if rule.get("hour") is not None and rule["hour"] != hour:
            return hour_match.group(0).strip()
    return None


def load_workflows(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "nodes" not in data and isinstance(data.get("data"), dict):
        data = data["data"]
    workflows = data if isinstance(data, list) else [data]
    for workflow in workflows:
        if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
            raise ValueError("not an n8n workflow export: expected an object with a nodes list")
    return workflows


LEDGER_ID = r"[NEXCSFKBRD]\d+[a-z]?"
BRANCH_PLACEHOLDER = "(list every branch of the operation's connector.yaml at the release tag)"
UNVERIFIED_NOTE = re.compile(
    r"(?i)\b(from memory|unverified|not (?:yet )?verified|unconfirmed|not (?:yet )?confirmed|assum(?:ed|ing|ptions?)|"
    r"probably|i recall|to be confirmed|needs? (?:source )?verification|confirm (?:in|against|at) (?:the )?(?:n8n )?source)\b"
)


def ledger_rows(text: str):
    """Yield (line number, cells) for rows of tables whose first header cell is ID."""
    in_ledger_table = False
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("|"):
            in_ledger_table = False
            continue
        cells = split_row(line)
        if cells and re.fullmatch(r"-{3,}", cells[0]):
            continue
        if cells and not re.fullmatch(LEDGER_ID, cells[0]):
            in_ledger_table = cells[0] == "ID"
            continue
        if in_ledger_table and len(cells) >= 3:
            yield number, cells


def split_row(line: str) -> list:
    cells = [part.strip() for part in re.split(r"(?<!\\)\|", line.strip())]
    return cells[1:-1] if len(cells) >= 2 else cells


def verify(path: Path, is_strict: bool = False, inventory_path: Path | None = None) -> int:
    problems, counts, seen, by_section = [], defaultdict(int), set(), defaultdict(lambda: defaultdict(int))
    text = path.read_text(encoding="utf-8")
    # A decision is defined by a Decisions table row, or by a bullet or heading that starts with its ID.
    decision_ids = set(re.findall(r"^(?:\|\s*|[-*]\s+(?:\*\*)?|#+\s+)(D\d+[a-z]?)\b", text, re.MULTILINE))
    for number, cells in ledger_rows(text):
        line = text.splitlines()[number - 1]
        seen.add(cells[0])
        status, notes = cells[-2].lower(), cells[-1]
        allowed = DECISION_STATUSES if cells[0].startswith("D") else STATUSES
        counts[status] += 1
        by_section[cells[0][0]][status] += 1
        for reference in sorted(set(re.findall(r"\bD\d+[a-z]?\b", notes)) - decision_ids):
            problems.append(f"line {number} {cells[0]}: notes cite {reference}, which is not in the Decisions table")
        if BRANCH_PLACEHOLDER in line:
            problems.append(f"line {number} {cells[0]}: replace the placeholder with one row per connector branch")
        elif status not in allowed:
            problems.append(f"line {number} {cells[0]}: status {status!r} is not one of {', '.join(allowed)}")
        elif status == "decided" and not notes:
            problems.append(f"line {number} {cells[0]}: decided needs the user's answer in notes")
        elif status == "mapped" and UNVERIFIED_NOTE.search(notes):
            problems.append(f"line {number} {cells[0]}: mapped rests on an unverified claim; cite the source or mark it blocked")
        elif status in NOTE_REQUIRED and not notes:
            problems.append(f"line {number} {cells[0]}: {status} needs notes")
        elif status == "pending" and is_strict:
            problems.append(f"line {number} {cells[0]}: pending awaits the user's decision")
    if not counts:
        problems.append("no ledger rows found")
    inventory_path = inventory_path or path.parent / "inventory.json"
    if not inventory_path.exists():
        print(f"warning: {inventory_path} not found, so deleted rows go undetected; keep inventory.json with the ledger or pass --inventory",
              file=sys.stderr)
    else:
        try:
            generated = json.loads(inventory_path.read_text(encoding="utf-8")).get("ledgerIds", [])
        except (OSError, ValueError):
            generated = []
        for row_id in generated:
            if row_id not in seen and not any(other.startswith(row_id) and other[len(row_id):].isalpha() for other in seen):
                problems.append(f"{row_id}: generated row is missing from the ledger (rows may be split, never deleted)")
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    if problems:
        print(f"ledger incomplete ({summary}):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    pending = counts.get("pending", 0)
    print(f"ledger complete: {summary}" + (f"; {pending} row(s) await the user's decision" if pending else ""))
    for section, statuses in sorted(by_section.items()):
        print(f"  {section}: " + ", ".join(f"{count} {status}" for status, count in sorted(statuses.items())))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    inventory_parser = commands.add_parser("inventory", help="write the fidelity ledger for an export")
    inventory_parser.add_argument("export", type=Path)
    inventory_parser.add_argument("--out", type=Path, help="directory for ledger.md and inventory.json")
    inventory_parser.add_argument("--catalog", type=Path, help="downloaded Dex connector catalog.yaml for the capability matrix")
    verify_parser = commands.add_parser("verify", help="check that every ledger row is resolved")
    verify_parser.add_argument("ledger", type=Path)
    verify_parser.add_argument("--strict", action="store_true", help="also fail while any row is pending")
    verify_parser.add_argument("--inventory", type=Path, help="inventory.json generated with this ledger (default: next to it)")
    arguments = parser.parse_args(argv)

    if arguments.command == "verify":
        return verify(arguments.ledger, arguments.strict, arguments.inventory)

    try:
        workflows = load_workflows(arguments.export)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    catalog = None
    if arguments.catalog is not None:
        try:
            catalog = load_catalog(arguments.catalog)
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
    for index, workflow in enumerate(workflows):
        inventory = Inventory(workflow, arguments.export.name, catalog).build()
        if arguments.out is None:
            print(inventory.to_markdown())
            continue
        directory = arguments.out if len(workflows) == 1 else arguments.out / f"workflow-{index + 1}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "ledger.md").write_text(inventory.to_markdown(), encoding="utf-8")
        (directory / "inventory.json").write_text(json.dumps(inventory.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {directory / 'ledger.md'} and {directory / 'inventory.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
