#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Capture golden values for one n8n expression parameter so a Go port can
// reproduce JavaScript's semantics, such as toLowerCase, trim, and replace.
//
// Usage: node n8n_expression_golden.mjs EXPORT.json "Node name" PARAMETER.PATH FIXTURE.json
//
// PARAMETER.PATH addresses the parameter inside the node's parameters, for
// example conditions.conditions[0].leftValue or fields.values[0].stringValue.
// FIXTURE.json uses the n8n_code_golden.mjs shape:
//   {"items": [{"json": {}}], "nodes": {"Setup": [{"json": {}}]},
//    "now": "2026-01-05T07:00:00-05:00", "timezone": "America/New_York"}
//
// Prints one JSON entry per item: {"value": ...} or {"error": "..."}. An error
// is golden behavior too: n8n fails the node when an expression throws. Read
// the expression before running it; the vm module is not a security boundary.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import vm from "node:vm";

function fail(message, exitCode = 2) {
  process.stderr.write(`error: ${message}\n`);
  process.exit(exitCode);
}

const [exportPath, nodeName, parameterPath, fixturePath] = process.argv.slice(2);
if (!exportPath || !nodeName || !parameterPath || !fixturePath) {
  fail('usage: node n8n_expression_golden.mjs EXPORT.json "Node name" PARAMETER.PATH FIXTURE.json');
}

const loaded = JSON.parse(readFileSync(exportPath, "utf8"));
const workflows = Array.isArray(loaded) ? loaded : [loaded.nodes ? loaded : loaded.data ?? loaded];
const node = workflows.flatMap((workflow) => workflow.nodes ?? []).find((candidate) => candidate.name === nodeName);
if (!node) fail(`node not found: ${nodeName}`);

let parameter = node.parameters ?? {};
for (const segment of parameterPath.match(/[^.[\]]+/g) ?? []) {
  parameter = parameter?.[/^\d+$/.test(segment) ? Number(segment) : segment];
}
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

let time = {};
if (/\$now|\$today|DateTime\b/.test(template)) {
  let luxon;
  try {
    luxon = createRequire(join(process.cwd(), "index.js"))("luxon");
  } catch {
    fail("the expression reads time through Luxon; run `npm install luxon` in the working directory first", 3);
  }
  if (!fixture.now) fail("the expression reads time; set fixture.now to a fixed ISO instant", 3);
  if (fixture.timezone) luxon.Settings.defaultZone = fixture.timezone;
  const now = luxon.DateTime.fromISO(fixture.now, { setZone: !fixture.timezone });
  time = { DateTime: luxon.DateTime, $now: now, $today: now.startOf("day") };
}

function nodeAccessor(name, index) {
  const nodeItems = otherNodes[name];
  if (!nodeItems) throw new Error(`fixture.nodes has no items for node ${JSON.stringify(name)}`);
  return {
    first: () => nodeItems[0],
    last: () => nodeItems[nodeItems.length - 1],
    all: () => nodeItems,
    get item() {
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
  return new vm.Script(`(${source})`).runInContext(sandbox, { timeout: 1000 });
}

const results = items.map((item, index) => {
  try {
    if (isSingleExpression) return { value: evaluate(segments[0][1], index, item) };
    let rendered = "";
    let position = 0;
    for (const segment of segments) {
      rendered += template.slice(position, segment.index);
      const value = evaluate(segment[1], index, item);
      if (value !== null && typeof value === "object") {
        throw new Error("an object inside a mixed template renders differently across n8n versions; capture it from an n8n execution");
      }
      rendered += String(value);
      position = segment.index + segment[0].length;
    }
    return { value: rendered + template.slice(position) };
  } catch (error) {
    return { error: String(error?.message ?? error) };
  }
});
process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
