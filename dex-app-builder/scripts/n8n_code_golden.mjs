#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Capture golden output from an n8n Code or Function node so that a Go port
// can prove parity.
//
// Usage: node n8n_code_golden.mjs EXPORT.json "Node name" FIXTURE.json
//
// FIXTURE.json:
//   {
//     "items": [{"json": {}}],              input items of the node
//     "nodes": {"Setup": [{"json": {}}]},   items of nodes read through $('Name')
//     "now": "2026-01-05T07:00:00-05:00",   required when the code reads time
//     "timezone": "America/New_York"         optional workflow timezone
//   }
//
// Prints the normalized output items as JSON on stdout; console output goes to
// stderr. A thrown error prints to stderr and exits 1, which is itself golden
// behavior: the n8n node fails. The code runs in a fresh vm context in sloppy
// mode, as the n8n Code node does. The vm module is not a security boundary:
// read the code before running it.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import vm from "node:vm";
import { inspect } from "node:util";

function fail(message, exitCode = 2) {
  process.stderr.write(`error: ${message}\n`);
  process.exit(exitCode);
}

const [exportPath, nodeName, fixturePath] = process.argv.slice(2);
if (!exportPath || !nodeName || !fixturePath) {
  fail('usage: node n8n_code_golden.mjs EXPORT.json "Node name" FIXTURE.json');
}

const loaded = JSON.parse(readFileSync(exportPath, "utf8"));
const workflows = Array.isArray(loaded) ? loaded : [loaded.nodes ? loaded : loaded.data ?? loaded];
const node = workflows.flatMap((workflow) => workflow.nodes ?? []).find((candidate) => candidate.name === nodeName);
if (!node) fail(`node not found: ${nodeName}`);

const kind = String(node.type).split(".").pop();
const parameters = node.parameters ?? {};
let code;
let mode;
if (kind === "code") {
  const language = parameters.language ?? "javaScript";
  if (language !== "javaScript") {
    fail(`unsupported Code language ${language}; capture golden output from an n8n execution instead`, 3);
  }
  code = parameters.jsCode ?? "";
  mode = parameters.mode ?? "runOnceForAllItems";
} else if (kind === "function") {
  code = parameters.functionCode ?? "";
  mode = "function";
} else if (kind === "functionItem") {
  code = parameters.functionCode ?? "";
  mode = "functionItem";
} else {
  fail(`node ${nodeName} is ${node.type}, not a Code or Function node`);
}

const toItem = (value) => (value && typeof value === "object" && "json" in value ? value : { json: value });
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
const items = (fixture.items ?? []).map(toItem);
const otherNodes = Object.fromEntries(
  Object.entries(fixture.nodes ?? {}).map(([name, nodeItems]) => [name, nodeItems.map(toItem)]),
);

let time = {};
if (/\$now|\$today|DateTime\b/.test(code)) {
  let luxon;
  try {
    luxon = createRequire(join(process.cwd(), "index.js"))("luxon");
  } catch {
    fail("the code reads time through Luxon; run `npm install luxon` in the working directory first", 3);
  }
  if (!fixture.now) fail("the code reads time; set fixture.now to a fixed ISO instant", 3);
  if (fixture.timezone) luxon.Settings.defaultZone = fixture.timezone;
  const now = luxon.DateTime.fromISO(fixture.now, { setZone: !fixture.timezone });
  time = { DateTime: luxon.DateTime, $now: now, $today: now.startOf("day") };
}

let positionalPairing = false;
function nodeAccessor(name, index) {
  const nodeItems = otherNodes[name];
  if (!nodeItems) throw new Error(`fixture.nodes has no items for node ${JSON.stringify(name)}`);
  return {
    first: () => nodeItems[0],
    last: () => nodeItems[nodeItems.length - 1],
    all: () => nodeItems,
    get item() {
      positionalPairing = true;
      return nodeItems[index] ?? nodeItems[0];
    },
    isExecuted: true,
  };
}

const format = (values) => values.map((value) => (typeof value === "string" ? value : inspect(value, { depth: 4 }))).join(" ");
const sandboxConsole = Object.fromEntries(
  ["log", "info", "warn", "error", "debug"].map((level) => [
    level,
    (...values) => process.stderr.write(`[console.${level}] ${format(values)}\n`),
  ]),
);

function context(index, item) {
  const perItem = mode === "runOnceForEachItem" || mode === "functionItem";
  return vm.createContext({
    $input: {
      all: () => items,
      first: () => items[0],
      last: () => items[items.length - 1],
      item: perItem ? item : undefined,
      params: parameters,
    },
    $json: perItem ? item?.json : undefined,
    $: (name) => nodeAccessor(name, index),
    $node: new Proxy({}, { get: (_, name) => ({ json: nodeAccessor(String(name), index).first()?.json }) }),
    items,
    item: mode === "functionItem" ? item?.json : perItem ? item : undefined,
    $itemIndex: index,
    $runIndex: 0,
    console: sandboxConsole,
    ...time,
  });
}

async function run(sandbox) {
  const script = new vm.Script(`(async () => {\n${code}\n})()`, { filename: `${nodeName}.js` });
  return script.runInContext(sandbox, { timeout: 5000 });
}

function normalize(result, perItem) {
  if (result === undefined || result === null) throw new Error("the code returned no value");
  if (perItem && Array.isArray(result)) throw new Error("runOnceForEachItem code must return one object, not an array");
  const entries = Array.isArray(result) ? result : [result];
  return entries.map((entry) => {
    if (entry === null || typeof entry !== "object") {
      throw new Error(`the code returned a non-object item: ${JSON.stringify(entry)}`);
    }
    if (!("json" in entry)) return { json: entry };
    return entry.binary ? { json: entry.json, binary: entry.binary } : { json: entry.json };
  });
}

const output = [];
try {
  if (mode === "runOnceForEachItem" || mode === "functionItem") {
    for (const [index, item] of items.entries()) {
      const result = await run(context(index, item));
      output.push(...(mode === "functionItem" ? [{ json: result }] : normalize(result, true)));
    }
  } else {
    output.push(...normalize(await run(context(0, items[0])), false));
  }
} catch (error) {
  process.stderr.write(`node failed: ${error?.stack ?? error}\n`);
  process.exit(1);
}

if (positionalPairing) {
  process.stderr.write("note: $('Node').item was resolved by position; confirm the paired-item lineage matches\n");
}
// Items are persisted as JSON in n8n, so undefined properties disappear.
process.stdout.write(`${JSON.stringify(JSON.parse(JSON.stringify(output)), null, 2)}\n`);
