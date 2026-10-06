# n8n export semantics for a Dex import

Read this with [workflow import](workflow-import.md). The defaults below tell you
what to check, not what to assume. Confirm each one in the n8n source at the
instance's release and the node's exported `typeVersion`; some engine defaults
change between releases without a `typeVersion` change.

## Export anatomy

- `nodes[]`: each node's `name` is unique and is how expressions refer to it.
  The node also has a `type` (`n8n-nodes-base.<node>`, a LangChain node, or a
  community package), `typeVersion`, `parameters`, and `credentials`. The
  credentials are only a credential type with an ID and a display name, never
  the secret. A reference without an ID, such as one marked
  `__aiGatewayManaged`, is an n8n-managed credential: nothing about the account
  carries over.
- `position` has no behavior, except that execution order `v1` runs fan-out
  branches top to bottom by it (see below).
- Execution settings on a node: `disabled`, `retryOnFail` with `maxTries`
  (default 3) and `waitBetweenTries` (default 1000 ms), `onError`
  (`stopWorkflow`, `continueRegularOutput`, or `continueErrorOutput`; the
  legacy form is `continueOnFail`), `alwaysOutputData`, and `executeOnce`.
- `connections`: keyed by source node name, then connection type (`main`, or
  `ai_*` for LangChain sub-nodes), then output index, then targets with the
  target's input `index`. IF output 0 is true and output 1 is false. Filter
  output 0 keeps items. Switch outputs follow rule order. Loop Over Items
  version 3 emits done on output 0 and loop on output 1.
- `settings`: `executionOrder`, `timezone`, `errorWorkflow`, and save and
  caller policies. When `timezone` is absent, the instance's
  `GENERIC_TIMEZONE` applies, and the export does not record which zone that
  is; an instance that never set it uses America/New_York.
- Provenance: `active` and `triggerCount` say whether a trigger was ever live
  (`triggerCount` 0 means no). `meta.templateId` marks a gallery template, a
  specification that may never have run, so there may be no execution history
  to compare against. `id` is the workflow ID; exports often omit it.
- `pinData` is editor test data, not production behavior, and may contain
  personal data. `staticData` is trigger runtime state, such as polling cursors
  and schedule recurrence, not configuration.
- A parameter value that starts with `=` is an expression. Each `{{ }}` segment
  is JavaScript, evaluated under the rules in
  [expressions](#parameter-expressions).

## Item model

- A node receives a list of items and runs its operation once per item by
  default. Each output item keeps a paired-item link to the input item that
  produced it.
- When a node outputs zero items, downstream nodes do not run, unless that node
  sets `alwaysOutputData`. A read that returns nothing ends that branch, and
  the execution succeeds. A downstream fallback for an empty list is dead code.
- A node that returns a provider collection field the response omits, as a
  not-found lookup often does, can emit one item with empty `json` instead of
  zero items. Downstream nodes then run with empty values; read the node's
  `execute()` to tell which.
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
- Reading a node that has not run, or a broken paired-item link, raises an n8n
  `ExpressionError`, which fails the node.
- Dex has no implicit lineage. Carry every upstream field a later Step reads in
  that Step's input or in the item's AttributeMap entry.

## Execution order and failure

- Before the first node runs, n8n checks every enabled node reachable from the
  start node over `main` connections for parameter issues: a required parameter
  that is displayed at the node's version and is empty, or an unknown node
  type. An expression counts as filled. If any node has an issue, the whole
  execution fails before any node runs, in every execution mode. Credentials
  are not part of this check. So an export with an empty required parameter
  anywhere downstream has no effect at all; record that as the source behavior
  and offer no "faithful" option that assumes later nodes run. A Webhook in
  `onReceived` mode has already answered the caller.
- Operation and other option values are not checked against the node's option
  list, before or during the run. What an unknown value does is node-specific:
  an explicit error, a lookup that throws, an `if` chain that makes no call and
  emits an empty item, or a request built from the remaining parameters. Read
  that node's `execute()` or routing at the release.
- Each node processes all of its items before the next node starts. Execution
  order `v1` runs each branch to completion before the next, ordered top to
  bottom by canvas position. Legacy `v0` interleaves nodes across branches. The
  order matters when branches have effects that interact: a failure in an
  earlier branch stops the later ones.
- A Wait pauses the whole execution, including sibling branches that have not
  run yet. A wait of 65 seconds or more saves the execution and resumes it
  later on the workflow snapshot taken when the execution started, so edits
  made during the wait do not apply to it. A shorter time wait sleeps inside
  the running execution.
- A failing node stops the execution unless its `onError` setting continues.
  Effects already performed remain, and later nodes run for no item. A Code
  node fails on a thrown error. A parameter expression usually does not: see
  [parameter expressions](#parameter-expressions).
- Nothing retries unless `retryOnFail` is set. An `errorWorkflow` runs a
  separate workflow with the error; map it to Execute-failure recovery Steps.
- Executions may overlap. Triggers other than the schedule do not deduplicate
  deliveries: a webhook starts one execution per request.

## Parameter expressions

- Expressions are JavaScript with Luxon. `$now`, and `$today` (the start of
  the day), use the workflow timezone and are evaluated separately in each
  node, so a Dex port decides which single instant replaces them, such as the
  occurrence time, and records it. Other globals include `DateTime`, `$json`,
  `$input`, `$('Name')`, `$vars`, `$env`, `$execution`, `$workflow`,
  `$itemIndex`, and `$runIndex`. `$vars` and `$env` values are not in the
  export.
- n8n's expression engine swallows every error inside a `{{ }}` segment except
  its own `ExpressionError` and syntax errors. A TypeError from calling a
  method on a missing field, such as `{{ $json.title.toLowerCase() }}` on an
  item without `title`, leaves that segment empty and the node continues; a
  whole-value expression yields `undefined`. Trace the empty value to its
  consumer: a predicate turns false, a provider call gets an empty parameter
  that can drop a filter, or a later node fails. The editor preview can show an
  error that a production run swallows.
- A whole-value expression returns its JavaScript value, including
  `undefined`. In a mixed template (text with segments), a segment that yields
  `null`, `undefined`, `NaN`, or an empty string renders as empty text;
  `false` and `0` render as text, objects as `[object Object]`, and arrays
  through `toString`, such as `1,,x`.
- An expression that returns a Luxon DateTime is serialized as ISO 8601 with
  its offset. Luxon macro formats such as `toFormat('DDD')` and
  `toLocaleString()` depend on the instance locale.
- Luxon maps to Go as follows. `toFormat('yyyy-MM-dd')` is
  `Format("2006-01-02")`. `plus` and `minus` with `days` are `AddDate` on a time
  in the same `*time.Location`. `startOf('day')` is `time.Date` at midnight in
  that location.
- IF, Filter, and Switch from version 2: null and undefined pass strict type
  validation. String operators compare `leftValue ?? ''`, and `exists` and
  `notExists` test null, undefined, and NaN. Only a present value of the wrong
  type fails strict validation. The golden harness does not evaluate
  operators, so write predicate expectations from `filter-parameter.ts` at the
  release and cite the lines.

## Code nodes

- A Code node runs in `runOnceForAllItems` mode by default and returns an array
  of items. In that mode, `$input.item` and `$json` return the first input item
  only. In `runOnceForEachItem` mode it returns one object per input item, and
  code that mentions `$input.all()`, `.first()`, `.last()`, or
  `.itemMatching()` is rejected before it runs.
- JavaScript semantics to preserve in a port:
  - A thrown error, such as a method call on a missing field, fails the node.
  - `String.replace` with a string pattern replaces only the first occurrence.
  - Template literals render `null` as `null`, `undefined` as `undefined`, and
    objects as `[object Object]`. `NaN` in an output item serializes as null.
  - `""`, `0`, `null`, and `undefined` are all falsy.
  - `toLowerCase`, `trim`, and `toLocaleString` differ from Go's standard
    library; port them with golden cases.
- `console.log` writes only to the execution log. The Code node runs sloppy-mode
  JavaScript, so an undeclared assignment creates a global instead of failing.

## Node mapping

| n8n node | Dex mapping |
| --- | --- |
| Schedule Trigger, legacy Cron, Interval | A scheduler Flow on the Cron pattern. It computes each next occurrence in the workflow's IANA zone, waits on a Timer, and starts one run Flow per occurrence. See [schedule rules](#schedule-rules). |
| Manual Trigger | Dex Web Start Flow with typed start input. |
| Webhook, Respond to Webhook | The webhook connector Trigger. Each n8n request starts one execution with one item `{headers, params, query, body, webhookUrl, executionMode}`; the Dex Trigger accepts only authenticated POST requests with a JSON or urlencoded body up to its size limit, takes its event ID from a delivery-ID header or body pointer, else a digest of the body, and so deduplicates a byte-identical re-POST while the Flow is retained. Read its request decoding at the tag. Record each difference; the authentication change is mandatory. A synchronous response body needs a capability check. |
| App Trigger, such as Gmail Trigger | The matching released connector Trigger, with the provider event ID as the request ID. If it is missing, contribute it. A trigger that accepts anyone, such as a Telegram Trigger without chat or user restrictions, is source behavior to record. |
| Form Trigger | A Dex Web Start Flow form, or a participant Custom UI when the form is participant-facing. |
| Error Trigger, workflow `errorWorkflow` | An Execute-failure route to an explicit recovery Step. |
| Set (Edit Fields) | A typed Go mapping inside the consuming application Step. |
| IF, Filter, Switch | A Go predicate in an application Step that chooses the movement. An unconnected output ends without a movement. |
| Merge | An await-all join with a Channel count, where each branch's success and failure routes both publish, so each branch counts once. Replicate the merge mode exactly: append, combine by key or position, or choose a branch. Under execution order `v1`, choose-branch requires inputs 1 and 2, so when one never receives items the Merge and everything after it never run and the execution ends without an error; the other modes run with the missing input empty. |
| Loop Over Items | Bounded dynamic parallel Steps, or batched Steps when the source paces a rate limit. |
| Split Out, Aggregate, Sort, Limit, Remove Duplicates, Date & Time | Pure Go transforms. Deduplication across executions needs durable state. |
| Code, Function, Function Item | A pure Go function in an application Step, with golden parity tests. |
| HTTP Request | The dedicated connector operation for that provider. The generic HTTP connector is only for an organization-controlled internal service. |
| Wait (`resume` timeInterval) | An application Step whose WaitFor returns `dex.Until(dex.Timer(amount × unit))`, measured from when that Step starts, as n8n measures from when the Wait node runs; its Execute builds the next Step's input. A Connector Step cannot wait. Never compute or persist a deadline in WaitFor. |
| Wait (`resume` specificTime) | An earlier application Step's Execute computes the instant from typed input in the workflow timezone; the waiting Step's Timer covers the remaining duration. |
| Wait (`resume` webhook or form) | A Channel or typed RPC resume. Without `limitWaitTime` (off by default), n8n waits forever. |
| Wait used as a delay before reading a submitted job's result | The Polling pattern with a bounded attempt count: a start Step, a Timer, a status Query Step, and completion. One Step execution makes one Connector call, so polling never happens inside one Step; without a released status operation the row is `blocked` on a connector gap. |
| Execute Workflow | Steps in the same Flow, or an independent top-level Flow under the Core boundary rules. Never a SubFlow by default. |
| No Operation, Sticky Note | No behavior. Mark it `dropped` and check what a note claims. |
| App node, such as Gmail, Google Calendar, or Slack | The released connector operation for the node's resource and operation. |
| LangChain agent, chain, or model | The `llm` connector `generateText` Query or a durable Dex agent; each tool becomes a Step. An agent without tools is one generation: its system message maps to instructions and its `output` to the generated text. |

When the source waits for hours or days, choose a versioning strategy from the
Dex SDK [versioning guide](../../dex-sdk/references/core/versioning.md) before
the first deploy, since Flows will be open across deploys.

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

  An absent `field` means `days`, and an omitted hour or minute is 0, because
  n8n fills declared defaults before the node runs. Each rule fires
  independently. The second is jittered on every rule except `seconds` and
  cron rules: a random second picked at each activation before n8n 2.19, and a
  stable per-node second from 2.19.
- A node name such as "Every morning" proves nothing. The inventory reports a
  mismatch between the name and the rule.
- Compare the schedule's interval with the time window each execution reads.
  When the window is longer, such as an hourly rule reading today's events,
  every execution repeats the same effects for the same records. That
  repetition is source behavior to record and decide on.
- Derive the run Flow ID from the scheduler's own Flow ID plus the occurrence,
  such as `<scheduler-flow-id>-run-2026-10-06` for a daily rule, and bind the
  request ID to that start. Flow IDs cannot contain `/`, `$`, or `:`, so do not
  embed an RFC 3339 time; a sub-daily rule appends a colon-free UTC time, such
  as `<scheduler-flow-id>-run-20261006T1409Z`, because a local time repeats in
  the DST fall-back hour. Scoping by the scheduler keeps two schedulers, such
  as one per calendar, from deduplicating each other's runs. Start with
  `IDReuseDisallow` and ignore-already-started, so a retried start lands on the
  same run.
- A manual "Execute workflow" maps to a run-now Action or Start Flow with its
  own identity, such as `<scheduler-flow-id>-run-manual-<request ID>`, so it
  never attaches to a closed occurrence run. Record it as an added capability.
- Decide what happens to an occurrence the Worker reaches late, such as after
  downtime. n8n's default scheduler never runs a missed occurrence, so skip one
  that is more than a bounded lateness old. The opt-in durable scheduler
  (`N8N_SCHEDULER_ENABLED`, from n8n 2.34) can run the latest missed one: from
  Schedule Trigger 1.4, `misfirePolicy` (default skip) and
  `misfireGraceSeconds` (0 means the instance's `N8N_SCHEDULER_MISFIRE_GRACE`,
  default 60 seconds) decide it. A lateness bound other than the source's is a
  `diverged` row.
- From n8n 2.19 (opt-in) and 2.28 (always), n8n deduplicates scheduled
  executions per workflow, node, and scheduled time; per-occurrence run
  identity reproduces that. Executions for different occurrences can still
  overlap.
- Give the waiting Step an explicit long Execute retry total duration. The
  default is four hours, so a longer Worker outage across an occurrence would
  fail that Step and end the scheduler.
- Decide how local times that a DST change skips or repeats are handled before
  you compute occurrences.

## Version-dependent defaults to confirm

| Node | What to confirm at the exported version |
| --- | --- |
| Set | Before 3.3, input fields pass through next to the set fields; from 3.3 they are dropped unless `includeOtherFields` is on. A field that resolves to null or undefined becomes the text `null` or `undefined` at 3.0, fails the node at 3.1 unless `ignoreConversionErrors` is on, and becomes null from 3.2. Binary data is dropped through 3.3 unless `includeBinary` is set, and from 3.4 is kept while input fields are kept. |
| Gmail send | From 2.1, the footer "This email was sent automatically with n8n" is appended unless `options.appendAttribution` is false; reply never appends it. `emailType` defaults to html (text before n8n 1.10), and html mail has no text/plain part at all. The message is trimmed. |
| Send Email | From 2.1, the same footer is appended unless `appendAttribution` is false. |
| Telegram send message | `parse_mode` is Markdown when unset, so the text is parsed as markup. From 1.1, "This message was sent automatically with n8n" is appended for Markdown or HTML unless `appendAttribution` is false; from 1.2, link previews are off by default. |
| Slack post or update | From 2.1, an "Automated with this n8n workflow" link is appended unless `includeLinkToWorkflow` is false. |
| Microsoft Teams create message | From 1.1, a "Powered by this n8n workflow" link is appended, as HTML, unless `includeLinkToWorkflow` is false. |
| Send-and-wait operations | They append an n8n attribution by default; check the release and the node. |
| Telegram Trigger | It accepts updates from anyone. Chat and user restrictions exist from 1.2; 1.1 shows them but ignores them. |
| Google Calendar event `getAll` | Without `returnAll`, it returns one page of `limit` events (default 50). The order is unspecified unless `options.orderBy` is set. |
| HTTP Request | From 3, every item's request starts at once and all are awaited together; `options.batching` only spaces the starts. A non-2xx response fails the node after every request settles, unless `neverError` is on. Without `options.timeout`, the timeout is 300,000 ms. Values concatenated into `url` are not form-encoded: spaces become `%20`, but `&`, `#`, and `+` in a value change the query. |
| Webhook | `httpMethod` defaults to GET, `authentication` to none, and `responseMode` to `onReceived`, which answers 200 `{"message":"Workflow was started"}`. A JSON body is parsed into `body`; urlencoded and multipart fields land in `body` as strings, multipart files in `binary`; from 1.1 an unparsed body becomes a binary file. |
| Wait | At 1, `amount` defaults to 1 and `unit` to hours; from 1.1, to 5 and seconds. A day is exactly 86,400 seconds, not a calendar day. |
| IF, Filter, Switch | From 2, strict type validation, case sensitivity, and the AND/OR combinator come from `conditions.options` and `combinator`; see [parameter expressions](#parameter-expressions) for null handling. |
| Code | The default mode, and the language (`javaScript` or Python). Python output cannot be captured by the golden harness. |
| LangChain model and option nodes | Option defaults can change between releases without a `typeVersion` change; record the release. |

## Credentials and identities

- Each credential type and account becomes a connection for the matching
  connector. Authorize it in Dex Web **Connectors** for local development; a
  deployed Dex Server uses project Connector configuration. When reading and
  sending use different accounts, keep two connections. Same-type nodes with
  different `authentication` settings may act for different accounts.
- A literal key in a parameter, such as an API key in a Set node or a URL, is
  a secret leak, not configuration. A key that travels from workflow data into
  a request URL, header, or body belongs to the connector connection. Follow
  the secure-first rules in
  [workflow import](workflow-import.md#2-secure-the-source-before-mapping-it).
