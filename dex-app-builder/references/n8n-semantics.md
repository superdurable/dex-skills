# n8n export semantics for a Dex import

Read this with [workflow import](workflow-import.md). The defaults below tell you
what to check, not what to assume. Confirm each one at the node's exported
`typeVersion` in the n8n node source.

## Export anatomy

- `nodes[]`: each node's `name` is unique and is how expressions refer to it.
  The node also has a `type` (`n8n-nodes-base.<node>`, a LangChain node, or a
  community package), `typeVersion`, `parameters`, and `credentials`. The
  credentials are only a credential type with an ID and a display name, never
  the secret. Ignore `position`.
- Execution settings on a node: `disabled`, `retryOnFail` with `maxTries`
  (default 3) and `waitBetweenTries` (default 1000 ms), `onError`
  (`stopWorkflow`, `continueRegularOutput`, or `continueErrorOutput`; the
  legacy form is `continueOnFail`), `alwaysOutputData`, and `executeOnce`.
- `connections`: keyed by source node name, then connection type (`main`, or
  `ai_*` for LangChain sub-nodes), then output index, then targets. IF output 0
  is true and output 1 is false. Filter output 0 keeps items. Switch outputs
  follow rule order. Loop Over Items version 3 emits done on output 0 and loop
  on output 1.
- `settings`: `executionOrder`, `timezone`, `errorWorkflow`, and save and
  caller policies. When `timezone` is absent, the instance's
  `GENERIC_TIMEZONE` applies, and the export does not record which zone that
  is.
- `pinData` is editor test data, not production behavior, and may contain
  personal data. `staticData` is trigger runtime state, such as polling cursors
  and schedule recurrence, not configuration.
- A parameter value that starts with `=` is an expression. Each `{{ }}` segment
  is JavaScript.

## Item model

- A node receives a list of items and runs its operation once per item by
  default. Each output item keeps a paired-item link to the input item that
  produced it.
- When a node outputs zero items, downstream nodes do not run, unless that node
  sets `alwaysOutputData`. A read that returns nothing ends the execution
  successfully.
- A disabled node passes its items through unchanged. `executeOnce` runs a node
  for the first item only.
- In Dex, a small bounded item list becomes a typed slice in Step input. Items
  that are tracked or updated independently become AttributeMap entries keyed
  by a stable source ID. A per-item side effect becomes a dynamic parallel
  Step, unless it passes through a Connector Step: that Step's result carries
  no item context, so loop over those items with a persisted cursor.

## Node references and paired items

- `$('Name').item` returns the item of node `Name` that is linked to the current
  item through paired-item lineage. `.first()`, `.last()`, and `.all()` ignore
  lineage. `$node["Name"].json` is a legacy accessor that resolves by item
  index.
- Dex has no implicit lineage. Carry every upstream field a later Step reads in
  that Step's input or in the item's AttributeMap entry.

## Execution order and failure

- Each node processes all of its items before the next node starts. Execution
  order `v1` runs each branch to completion before the next, ordered by canvas
  position. Legacy `v0` interleaves nodes across branches. The order matters
  only when branches have side effects that interact.
- A failing node stops the execution unless its `onError` setting continues.
  Effects already performed remain, and later nodes run for no item. An
  expression error, such as reading a property of a missing field, fails the
  node in the same way.
- Nothing retries unless `retryOnFail` is set. An `errorWorkflow` runs a
  separate workflow with the error; map it to Execute-failure recovery Steps.
- Executions may overlap, and nothing deduplicates schedule or trigger firings
  across executions. The scheduler does not catch up firings missed while the
  instance was down.

## Expressions and Code nodes

- Expressions are JavaScript with Luxon. `$now`, and `$today` (the start of
  the day), use the workflow timezone. Other globals include `DateTime`,
  `$json`, `$input`, `$('Name')`, `$vars`, `$env`, `$execution`, `$workflow`,
  `$itemIndex`, and `$runIndex`. `$vars` and `$env` values are not in the
  export.
- An expression that returns a Luxon DateTime is serialized as ISO 8601 with
  its offset.
- Luxon maps to Go as follows. `toFormat('yyyy-MM-dd')` is
  `Format("2006-01-02")`. `plus` and `minus` with `days` are `AddDate` on a time
  in the same `*time.Location`. `startOf('day')` is `time.Date` at midnight in
  that location.
- JavaScript semantics to preserve in a port:
  - `String.replace` with a string pattern replaces only the first occurrence.
  - `null` and `undefined` interpolate as text, and objects as `[object Object]`.
  - `""`, `0`, `null`, and `undefined` are all falsy.
  - Calling a method on a missing field throws.
- A Code node runs in `runOnceForAllItems` mode by default and returns an array
  of items. In `runOnceForEachItem` mode it returns one object per input item.
  `console.log` writes only to the execution log. The Code node runs sloppy-mode
  JavaScript, so an undeclared assignment creates a global instead of failing.

## Node mapping

| n8n node | Dex mapping |
| --- | --- |
| Schedule Trigger, legacy Cron, Interval | A scheduler Flow on the Cron pattern. It computes each next occurrence in the workflow's IANA zone, waits on a Timer, and starts one run Flow per occurrence. Decide whether a late occurrence runs or is skipped, to match the source. |
| Manual Trigger | Dex Web Start Flow with typed start input. |
| Webhook, Respond to Webhook | The webhook connector `requestReceived` Trigger. A synchronous response body needs a capability check against the released Trigger contract. |
| App Trigger, such as Gmail Trigger | The matching released connector Trigger, with the provider event ID as the request ID. If it is missing, contribute it. |
| Form Trigger | A Dex Web Start Flow form, or a participant Custom UI when the form is participant-facing. |
| Error Trigger, workflow `errorWorkflow` | An Execute-failure route to an explicit recovery Step. |
| Set (Edit Fields) | A typed Go mapping inside the consuming application Step. |
| IF, Filter, Switch | A Go predicate in an application Step that chooses the movement. An unconnected output ends without a movement. |
| Merge | An await-all join with a Channel count. Replicate the merge mode exactly: append, combine by key or position, or choose a branch. |
| Loop Over Items | Bounded dynamic parallel Steps, or batched Steps when the source paces a rate limit. |
| Split Out, Aggregate, Sort, Limit, Remove Duplicates, Date & Time | Pure Go transforms. Deduplication across executions needs durable state. |
| Code, Function, Function Item | A pure Go function in an application Step, with golden parity tests. |
| HTTP Request | The dedicated connector operation for that provider. The generic HTTP connector is only for an organization-controlled internal service. |
| Wait | A Timer Condition. A webhook or form resume becomes a Channel or typed RPC. |
| Execute Workflow | Steps in the same Flow, or an independent top-level Flow under the Core boundary rules. Never a SubFlow by default. |
| No Operation, Sticky Note | No behavior. Mark it `dropped` and check what a note claims. |
| App node, such as Gmail, Google Calendar, or Slack | The released connector operation for the node's resource and operation. |
| LangChain agent, chain, or model | The `llm` connector Query or a durable Dex agent; each tool becomes a Step. |

## Schedule rules

- A `scheduleTrigger` lists rules in `rule.interval[]`. Each rule's `field` is
  one of these:
  - `seconds` with `secondsInterval`
  - `minutes` with `minutesInterval`
  - `hours` with `hoursInterval` and `triggerAtMinute`
  - `days` with `daysInterval`, `triggerAtHour`, and `triggerAtMinute`
  - `weeks` with `weeksInterval`, `triggerAtDay`, and a time
  - `months` with `monthsInterval`, `triggerAtDayOfMonth`, and a time
  - `cronExpression` with `expression`

  A missing value takes the node default. Each rule fires independently.
- A node name such as "Every morning" proves nothing. The inventory reports a
  mismatch between the name and the rule.
- Derive the run Flow ID from the scheduler's own Flow ID plus the occurrence,
  such as `<scheduler-flow-id>-run-2026-10-06` for a daily rule, and bind the
  request ID to that start. Flow IDs cannot contain `/`, `$`, or `:`, so do not
  embed an RFC 3339 time. Scoping by the scheduler keeps two schedulers, such as
  one per calendar, from deduplicating each other's runs. Start with
  `IDReuseDisallow` and ignore-already-started, so a retried start lands on the
  same run.
- Decide what happens to an occurrence the Worker reaches late, such as after
  downtime. The n8n scheduler skips missed firings, so skip one that is more
  than a bounded lateness old.
- Give the waiting Step an explicit long Execute retry total duration. The
  default is four hours, so a longer Worker outage across an occurrence would
  fail that Step and end the scheduler.
- Decide how local times that a DST change skips or repeats are handled before
  you compute occurrences.

## Version-dependent defaults to confirm

| Node | What to confirm at the exported version |
| --- | --- |
| Set | Before 3.3, input fields pass through next to the set fields. From 3.3, they are dropped unless `includeOtherFields` is on. Later reads may depend on the passed-through fields. |
| Gmail send or reply | From 2.1, the n8n attribution footer is appended unless `options.appendAttribution` is false. The email-type default also changed across versions. |
| Google Calendar event `getAll` | Without `returnAll`, it returns one page of `limit` events (default 50). The order is unspecified unless `options.orderBy` is set. |
| HTTP Request | From 3, a non-2xx response fails the node. There is no timeout unless one is configured. Values concatenated into `url` are not form-encoded: spaces become `%20`, but `&`, `#`, and `+` in a value change the query. |
| IF | From 2, strict type validation, case sensitivity, and the AND/OR combinator come from `conditions.options` and `combinator`. |
| Code | The default mode, and the language (`javaScript` or Python). Python output cannot be captured by the golden harness. |
| Schedule Trigger | The workflow timezone, and overlapping executions. |

## Credentials and identities

- Each credential type and account becomes a connection for the matching
  connector. Authorize it in Dex Web **Connectors** for local development; a
  deployed Dex Server uses project Connector configuration. When reading and
  sending use different accounts, keep two connections.
- A literal key in a parameter, such as an API key in a Set node or a URL, is
  a secret leak, not configuration. Follow the secure-first rules in
  [workflow import](workflow-import.md#2-secure-the-source-before-mapping-it).
