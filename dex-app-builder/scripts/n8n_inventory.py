#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inventory an n8n workflow export into a Dex import fidelity ledger.

Usage:
  n8n_inventory.py inventory EXPORT.json [--out DIRECTORY]
  n8n_inventory.py verify LEDGER.md

``inventory`` enumerates every node, connection, expression, credential
reference, literal secret, workflow setting, and known version-dependent
default, then writes ``ledger.md`` and ``inventory.json`` (or prints the ledger
when no directory is given). Literal secrets are redacted everywhere.

``verify`` fails while a ledger row is still ``todo`` or while a ``diverged``,
``dropped``, or ``blocked`` row has no notes.

The export is untrusted data: nothing in it is executed or followed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

STATUSES = ("mapped", "diverged", "dropped", "blocked")
NOTE_REQUIRED = ("diverged", "dropped", "blocked")
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
    r"\$json\.[A-Za-z_$][\w$]*\.(toLowerCase|toUpperCase|trim|split|replace|"
    r"startsWith|endsWith|includes|match)\("
)
TEMPLATE_INTERPOLATION = re.compile(r"\$\{([^{}]*)\}")

TRIGGER_TYPES = {
    "scheduleTrigger", "cron", "interval", "manualTrigger", "start", "webhook",
    "formTrigger", "errorTrigger", "executeWorkflowTrigger", "n8nTrigger",
    "chatTrigger",
}
DEX_HINTS = {
    "scheduleTrigger": "Scheduler Flow on the Cron pattern: a Timer to the next occurrence in the source timezone starts one run Flow per occurrence, with the Flow ID derived from the occurrence instant.",
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

DEFAULT_RESOURCE = {"googleCalendar": "event", "gmail": "message", "slack": "message"}


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
    def __init__(self, workflow: dict, source_name: str):
        self.workflow = workflow
        self.source_name = source_name
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

    # ----- collection -------------------------------------------------
    def build(self) -> "Inventory":
        self.collect_edges()
        self.collect_secrets()
        for node in self.nodes:
            self.collect_node(node)
        self.emit_grouped()
        self.check_reachability()
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
            elif kind == "missing-field-throws":
                self.add_finding("medium", kind, node,
                                 f"Calls a string method on an unguarded field: {listed}. An item missing that field fails the node and the whole execution; decide whether Dex reproduces the failure or treats it as a non-match.")
            elif kind == "hardcoded-address":
                self.add_finding("medium", kind, node,
                                 f"Literal address(es) {listed}; make them configuration or typed start input.")

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

        for field in self.node_set_fields(node):
            self.set_fields.append({"node": name, **field})
            if field["type"] == "numberValue" and isinstance(field["value"], str):
                self.add_finding("info", "type-coercion", name,
                                 f"Field `{field['name']}` is a number field holding the string {field['value']!r}; n8n coerces it to a number.")

        for path, value in walk(parameters):
            if isinstance(value, str) and value.startswith("="):
                self.collect_expression(node, path, value)
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
        if kind == "httpRequest" or (self.is_app_node(node) and not is_trigger(node)):
            if not node.get("retryOnFail"):
                self.add_finding("info", "no-retry", name,
                                 "n8n does not retry this call (retryOnFail is off); a Dex connector retries per its execution policy. Record that divergence.")

        self.node_rows.append({
            "node": name,
            "type": f"{kind}@{version:g}",
            "behavior": self.describe(node),
            "hint": self.hint(node),
        })

    def is_app_node(self, node: dict) -> bool:
        kind = short_type(node.get("type", ""))
        package = node.get("type", "").rsplit(".", 1)[0]
        return package == "n8n-nodes-base" and kind not in DEX_HINTS and kind not in TRIGGER_TYPES

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
            operation = parameters.get("operation", "")
            if resource or operation:
                parts.append("/".join(part for part in (resource, operation) if part))
            for key, value in parameters.items():
                if key in ("resource", "operation", "options"):
                    continue
                if isinstance(value, dict) and value.get("__rl"):
                    parts.append(f"{key}={value.get('value')} (fixed resource)")
                elif isinstance(value, (str, int, float, bool)) and value != "":
                    parts.append(f"{key}={self.short_value(value, 80)}")
            options = parameters.get("options")
            if isinstance(options, dict):
                parts.append("options: " + (", ".join(sorted(options)) or "none (all defaults)"))
        return "; ".join(part for part in parts if part)

    @staticmethod
    def short_value(value, limit: int = 60) -> str:
        text = json.dumps(value) if not isinstance(value, str) else value
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
        if ENVIRONMENT.search(body):
            semantics.append("reads instance environment or variables")
            self.add_finding("high", "environment", name,
                             f"`{path}` reads $env/$vars/$secrets, which the export does not contain; map each to configuration.")
        for match in STRING_REPLACE.finditer(body):
            semantics.append(f"String.replace({match.group(2)!r}) replaces only the first occurrence")
        if UNGUARDED_METHOD.search(body):
            semantics.append("throws when the field is missing (fails the node)")
            self.group("missing-field-throws", name, path)
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
                             + "; JavaScript renders null as 'null', undefined as 'undefined', and objects as '[object Object]'. The Go port must match the golden output.")
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
        elif kind == "gmail" and version >= 2.1 and parameters.get("operation", "send") in ("send", "reply"):
            if options.get("appendAttribution", True):
                note = "Gmail v2.1+ appends the n8n attribution footer unless options.appendAttribution is false; the email type default also changed between versions. Verify at this typeVersion and record the footer as a divergence."
        elif kind == "googleCalendar" and parameters.get("operation") == "getAll":
            if not parameters.get("returnAll"):
                note = f"Google Calendar getAll returns one page of {parameters.get('limit', 50)} events (default 50) without paging; order is unspecified unless options.orderBy is set."
        elif kind == "httpRequest" and version >= 3:
            if not options.get("response", {}).get("response", {}).get("neverError"):
                note = "HTTP Request v3+: a non-2xx response fails the node and the execution; there is no explicit timeout unless options.timeout is set."
        elif kind == "if" and version >= 2:
            note = "IF v2: strict type validation and expression errors fail the node and the execution; only the true and false outputs exist."
        elif kind == "code":
            note = f"Code v2 mode is {parameters.get('mode', 'runOnceForAllItems')}; runOnceForEachItem returns one item per input item."
        elif kind == "scheduleTrigger":
            note = "Schedule Trigger fires in the workflow timezone (settings.timezone, else the instance GENERIC_TIMEZONE); overlapping executions are allowed."
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
                                     + (f", and {unused} can never match." if unused else "."))

    def check_settings(self) -> None:
        settings = self.workflow.get("settings", {}) or {}
        if not settings.get("timezone"):
            if any(item["kind"] in ("timezone-dependent", "version-default") and "timezone" in item["message"] for item in self.findings) or self.schedules:
                self.add_finding("high", "timezone-unset", "(workflow)",
                                 "settings.timezone is absent, so schedules, $today, and $now use the n8n instance default (GENERIC_TIMEZONE). The export cannot tell which zone; ask the user.")
        if settings.get("errorWorkflow"):
            self.add_finding("high", "error-workflow", "(workflow)",
                             "An error workflow handles failures; map it to Execute-failure recovery Steps.")
        if self.workflow.get("pinData"):
            self.add_finding("info", "pin-data", "(workflow)",
                             "pinData holds editor test data, not production behavior; it may contain personal data. Use it only to shape synthetic fixtures.")

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
            "Set every Status cell to `mapped`, `diverged`, `dropped`, or `blocked`. "
            "`diverged`, `dropped`, and `blocked` rows need Notes that record the reason or the user's decision. "
            "Then run `n8n_inventory.py verify` on this file.",
            "",
            "## Summary",
            "",
            f"- Triggers: {', '.join(row['node'] + ' (' + row['type'] + ')' for row in triggers) or 'none'}",
            f"- Integrations: {', '.join(row['node'] + ' (' + row['type'] + ')' for row in integrations) or 'none'}",
            f"- Code nodes: {', '.join(row['node'] for row in code_nodes) or 'none'}",
            f"- Findings: {counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['info']} info",
            "",
            "## Execution graph",
            "",
            "| From | Output | To |",
            "| --- | --- | --- |",
        ]
        for edge in self.edges:
            lines.append(f"| {cell(edge['from'])} | {cell(edge['label'])} | {cell(edge['to'])} |")
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
        settings = self.workflow.get("settings", {}) or {}
        lines += ["", "## Workflow settings", "", "| ID | Setting | Value | Status | Notes |", "| --- | --- | --- | --- | --- |"]
        setting_rows = [("timezone", settings.get("timezone", "(absent: instance default)"))]
        setting_rows += [(key, value) for key, value in settings.items() if key != "timezone"]
        for index, (key, value) in enumerate(setting_rows, 1):
            lines.append(f"| S{index} | {cell(key)} | {cell(json.dumps(value) if not isinstance(value, str) else value)} | todo |   |")
        lines += ["", "## Findings", "", "| ID | Severity | Kind | Node | Finding | Status | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for index, finding in enumerate(self.findings, 1):
            lines.append(
                f"| F{index} | {finding['severity']} | {finding['kind']} | {cell(finding['node'])} | {cell(finding['message'], 420)} | todo |   |"
            )
        lines += ["", "## Claims to check against behavior", ""]
        for claim in self.claims:
            lines.append(f"- {claim['source']}: {cell(claim['text'], 400)}")
        if not self.claims:
            lines.append("- none")
        decisions = [item for item in self.findings if item["severity"] in ("critical", "high")]
        lines += ["", "## Decisions for the user", ""]
        for index, finding in enumerate(decisions, 1):
            lines.append(f"{index}. [{finding['kind']}] {finding['node']}: {cell(finding['message'], 420)}")
        if not decisions:
            lines.append("None from the inventory; add any found during the semantic review.")
        lines.append("")
        return self.redact("\n".join(lines))


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


def split_row(line: str) -> list:
    cells = [part.strip() for part in re.split(r"(?<!\\)\|", line.strip())]
    return cells[1:-1] if len(cells) >= 2 else cells


def verify(path: Path) -> int:
    problems, counts = [], defaultdict(int)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) < 3 or not re.fullmatch(r"[NXCSF]\d+", cells[0]):
            continue
        status, notes = cells[-2].lower(), cells[-1]
        counts[status] += 1
        if status not in STATUSES:
            problems.append(f"line {number} {cells[0]}: status {status!r} is not one of {', '.join(STATUSES)}")
        elif status in NOTE_REQUIRED and not notes:
            problems.append(f"line {number} {cells[0]}: {status} needs notes")
    if not counts:
        problems.append("no ledger rows found")
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    if problems:
        print(f"ledger incomplete ({summary}):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"ledger complete: {summary}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    inventory_parser = commands.add_parser("inventory", help="write the fidelity ledger for an export")
    inventory_parser.add_argument("export", type=Path)
    inventory_parser.add_argument("--out", type=Path, help="directory for ledger.md and inventory.json")
    verify_parser = commands.add_parser("verify", help="check that every ledger row is resolved")
    verify_parser.add_argument("ledger", type=Path)
    arguments = parser.parse_args(argv)

    if arguments.command == "verify":
        return verify(arguments.ledger)

    try:
        workflows = load_workflows(arguments.export)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for index, workflow in enumerate(workflows):
        inventory = Inventory(workflow, arguments.export.name).build()
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
