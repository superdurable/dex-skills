#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Capture golden output from an n8n Code or Function node so that a Go port
// can prove parity.
//
// Usage: node n8n_code_golden.mjs EXPORT.json "Node name" FIXTURE.json [--luxon DIRECTORY]
//
// FIXTURE.json:
//   {
//     "items": [{"json": {}}],              input items of the node
//     "nodes": {"Setup": [{"json": {}}]},   items of nodes read through $('Name')
//     "now": "2026-01-05T07:00:00-05:00",   required when the code reads time
//     "timezone": "America/New_York"         optional workflow timezone
//   }
//
// In Run Once for All Items mode, $input.item and $json read the first input
// item, as in n8n. In Run Once for Each Item mode, code that mentions
// $input.all(), .first(), .last(), or .itemMatching() is rejected before it
// runs, as in n8n.
//
// Prints the normalized output items as JSON on stdout; console output goes to
// stderr. A thrown error prints to stderr and exits 1, which is itself golden
// behavior: the n8n node fails. The code runs in a fresh vm context in sloppy
// mode, as the n8n Code node does. The vm module is not a security boundary:
// read the code before running it.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { inspect } from "node:util";

function fail(message, exitCode = 2) {
  process.stderr.write(`error: ${message}\n`);
  process.exit(exitCode);
}

const argumentsList = process.argv.slice(2);
const luxonIndex = argumentsList.indexOf("--luxon");
const luxonDirectory = luxonIndex >= 0 ? argumentsList.splice(luxonIndex, 2)[1] : undefined;
const [exportPath, nodeName, fixturePath] = argumentsList;
if (!exportPath || !nodeName || !fixturePath) {
  fail('usage: node n8n_code_golden.mjs EXPORT.json "Node name" FIXTURE.json [--luxon DIRECTORY]');
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
if (/\$now|\$today|DateTime\b/.test(code)) {
  const luxon = loadLuxon("the code");
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

let firstItemOnly = false;
function context(index, item) {
  const perItem = mode === "runOnceForEachItem" || mode === "functionItem";
  const firstItem = () => {
    firstItemOnly = true;
    if (items.length === 0) throw new Error("No execution data available");
    return items[0];
  };
  return vm.createContext({
    $input: {
      all: () => items,
      first: () => items[0],
      last: () => items[items.length - 1],
      get item() {
        return perItem ? item : mode === "runOnceForAllItems" ? firstItem() : undefined;
      },
      params: parameters,
    },
    get $json() {
      return perItem ? item?.json : mode === "runOnceForAllItems" ? firstItem().json : undefined;
    },
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

if (mode === "runOnceForEachItem") {
  for (const line of code.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*")) continue;
    const match = trimmed.match(/\$input\.(all|first|last|itemMatching)\b/);
    if (match) {
      process.stderr.write(`node failed: Can't use .${match[1]}() here: this is only available in 'Run Once for All Items' mode\n`);
      process.exit(1);
    }
  }
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

if (firstItemOnly) {
  process.stderr.write("note: $input.item or $json in 'Run Once for All Items' mode read only the first input item, as n8n does\n");
}
if (positionalPairing) {
  process.stderr.write("note: $('Node').item was resolved by position; confirm the paired-item lineage matches\n");
}
// Items are persisted as JSON in n8n, so undefined properties disappear.
process.stdout.write(`${JSON.stringify(JSON.parse(JSON.stringify(output)), null, 2)}\n`);
