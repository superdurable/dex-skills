#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Capture golden values for one n8n expression parameter so a Go port can
// reproduce JavaScript's semantics, such as toLowerCase, trim, and replace.
//
// Usage: node n8n_expression_golden.mjs EXPORT.json "Node name" PARAMETER.PATH FIXTURE.json [--expression "={{ ... }}"]
//
// PARAMETER.PATH addresses the parameter inside the node's parameters, for
// example conditions.conditions[0].leftValue or fields.values[0].stringValue.
// FIXTURE.json uses the n8n_code_golden.mjs shape:
//   {"items": [{"json": {}}], "nodes": {"Setup": [{"json": {}}]},
//    "now": "2026-01-05T07:00:00-05:00", "timezone": "America/New_York"}
//
// --expression evaluates a proposed replacement, such as a fix the user must
// approve, in place of the exported value of PARAMETER.PATH.
//
// Prints one JSON entry per item: {"value": ...}, {"undefined": true} when a
// whole-value expression yields undefined (the node receives undefined), or
// {"error": "..."} when n8n fails the node. n8n's expression engine swallows
// every error except its own ExpressionError (such as reading a node that has
// not run) and syntax errors: a TypeError from a method call on a missing field
// leaves that segment empty and the node continues. Such entries carry
// "swallowedErrors"; record the empty value's downstream effect, not a failure.
// Inside a mixed template, a segment that yields null, undefined, NaN, or an
// empty string renders as empty text; false and 0 render as text, and objects
// render through String(), such as [object Object]. Read the expression before
// running it; the vm module is not a security boundary.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

function fail(message, exitCode = 2) {
  process.stderr.write(`error: ${message}\n`);
  process.exit(exitCode);
}

const argumentsList = process.argv.slice(2);
function takeOption(name) {
  const index = argumentsList.indexOf(name);
  if (index < 0) return undefined;
  const value = argumentsList.splice(index, 2)[1];
  if (value === undefined) fail(`${name} needs a value`);
  return value;
}
const override = takeOption("--expression");
const luxonDirectory = takeOption("--luxon");
const [exportPath, nodeName, parameterPath, fixturePath] = argumentsList;
if (!exportPath || !nodeName || !parameterPath || !fixturePath) {
  fail('usage: node n8n_expression_golden.mjs EXPORT.json "Node name" PARAMETER.PATH FIXTURE.json [--expression "={{ ... }}"]');
}

const loaded = JSON.parse(readFileSync(exportPath, "utf8"));
const workflows = Array.isArray(loaded) ? loaded : [loaded.nodes ? loaded : loaded.data ?? loaded];
const node = workflows.flatMap((workflow) => workflow.nodes ?? []).find((candidate) => candidate.name === nodeName);
if (!node) fail(`node not found: ${nodeName}`);

let parameter = node.parameters ?? {};
for (const segment of parameterPath.match(/[^.[\]]+/g) ?? []) {
  parameter = parameter?.[/^\d+$/.test(segment) ? Number(segment) : segment];
}
if (override !== undefined) parameter = override;
if (typeof parameter !== "string" || !parameter.startsWith("=")) {
  fail(`${parameterPath} is not an expression parameter`);
}
const template = parameter.slice(1);
const segments = [...template.matchAll(/\{\{([\s\S]*?)\}\}/g)];
const isSingleExpression = segments.length === 1 && segments[0][0].length === template.trim().length;

const toItem = (value) => (value && typeof value === "object" && "json" in value ? value : { json: value });
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
const items = (fixture.items ?? []).map(toItem);
const otherNodes = Object.fromEntries(
  Object.entries(fixture.nodes ?? {}).map(([name, nodeItems]) => [name, nodeItems.map(toItem)]),
);

// Luxon resolves from --luxon DIRECTORY, N8N_GOLDEN_LUXON, the working directory, this script's directory, or NODE_PATH.
function loadLuxon(reason) {
  const directories = [luxonDirectory, process.env.N8N_GOLDEN_LUXON, process.cwd(), dirname(fileURLToPath(import.meta.url)),
    ...(process.env.NODE_PATH ?? "").split(delimiter)].filter(Boolean);
  for (const directory of directories) {
    try {
      return createRequire(join(directory, "index.js"))("luxon");
    } catch {}
  }
  fail(`${reason} reads time through Luxon, which was not found in ${directories.join(", ")}. Run \`npm install --prefix DIRECTORY luxon@VERSION\` with the Luxon version that packages/workflow/package.json pins at the source n8n release, then pass --luxon DIRECTORY`, 3);
}

let time = {};
if (/\$now|\$today|DateTime\b/.test(template)) {
  const luxon = loadLuxon("the expression");
  if (!fixture.now) fail("the expression reads time; set fixture.now to a fixed ISO instant", 3);
  if (fixture.timezone) luxon.Settings.defaultZone = fixture.timezone;
  const now = luxon.DateTime.fromISO(fixture.now, { setZone: !fixture.timezone });
  time = { DateTime: luxon.DateTime, $now: now, $today: now.startOf("day") };
}

// n8n raises an ExpressionError, which fails the node, when an expression reads a node that has not run.
class ExpressionError extends Error {
  name = "ExpressionError";
}

let positionalPairing = false;
function nodeAccessor(name, index) {
  const nodeItems = otherNodes[name];
  if (!nodeItems) throw new ExpressionError(`Referenced node ${JSON.stringify(name)} has no items in fixture.nodes (in n8n: the node has not been executed)`);
  return {
    first: () => nodeItems[0],
    last: () => nodeItems[nodeItems.length - 1],
    all: () => nodeItems,
    get item() {
      positionalPairing = true;
      return nodeItems[index] ?? nodeItems[0];
    },
  };
}

function evaluate(source, index, item) {
  const sandbox = vm.createContext({
    $json: item.json,
    $input: { item, all: () => items, first: () => items[0], last: () => items[items.length - 1] },
    $: (name) => nodeAccessor(name, index),
    $node: new Proxy({}, { get: (_, name) => ({ json: nodeAccessor(String(name), index).first()?.json }) }),
    $itemIndex: index,
    ...time,
  });
  let script;
  try {
    script = new vm.Script(`(${source})`);
  } catch (error) {
    throw new ExpressionError(`invalid syntax: ${error.message}`);
  }
  try {
    return { value: script.runInContext(sandbox, { timeout: 1000 }) };
  } catch (error) {
    if (error?.name === "ExpressionError") throw error;
    return { swallowed: String(error?.message ?? error) };
  }
}

const results = items.map((item, index) => {
  try {
    if (isSingleExpression) {
      const { value, swallowed } = evaluate(segments[0][1], index, item);
      if (swallowed !== undefined) return { undefined: true, swallowedErrors: [swallowed] };
      if (value === undefined) return { undefined: true };
      if (typeof value === "number" && !Number.isFinite(value)) return { value: String(value), note: "not representable in JSON" };
      return { value };
    }
    let rendered = "";
    let position = 0;
    const swallowedErrors = [];
    for (const segment of segments) {
      rendered += template.slice(position, segment.index);
      const { value, swallowed } = evaluate(segment[1], index, item);
      if (swallowed !== undefined) swallowedErrors.push(swallowed);
      // n8n's template engine keeps a segment only when value || value === 0 || value === false, then joins.
      rendered += value || value === 0 || value === false ? String(value) : "";
      position = segment.index + segment[0].length;
    }
    const entry = { value: rendered + template.slice(position) };
    return swallowedErrors.length ? { ...entry, swallowedErrors } : entry;
  } catch (error) {
    return { error: String(error?.message ?? error) };
  }
});
if (positionalPairing) {
  process.stderr.write("note: $('Node').item was resolved by position; confirm the paired-item lineage matches\n");
}
process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
